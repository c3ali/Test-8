from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Query, Path, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import timedelta
import json
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List
from models import User, Board, List, Card, Label, Comment, BoardMember
from schemas import (
    Token, TokenRefresh, UserCreate, UserUpdate, UserResponse,
    BoardCreate, BoardUpdate, BoardResponse, ListCreate, ListUpdate,
    ListResponse, CardCreate, CardUpdate, CardResponse, LabelCreate,
    LabelResponse, CommentCreate, CommentUpdate, CommentResponse,
    CardMove, BoardMemberAdd
)
from database import get_db, init_db
from middleware.auth import (
    create_access_token, create_refresh_token, verify_token,
    get_current_user, get_current_active_user, get_current_user_optional,
    rotate_refresh_token, setup_auth
)
from middleware.cors import setup_cors
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
app = FastAPI(title="Trello Clone API", version="1.0.0")
setup_cors(app)
setup_auth(app)
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, board_id: str):
        await websocket.accept()
        if board_id not in self.active_connections:
            self.active_connections[board_id] = []
        self.active_connections[board_id].append(websocket)
    def disconnect(self, websocket: WebSocket, board_id: str):
        if board_id in self.active_connections:
            self.active_connections[board_id].remove(websocket)
            if not self.active_connections[board_id]:
                del self.active_connections[board_id]
    async def broadcast(self, message: dict, board_id: str):
        if board_id in self.active_connections:
            for connection in self.active_connections[board_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass
manager = ConnectionManager()
def check_board_permission(board_id: int, user: User, db: Session, require_admin: bool = False):
    board = db.query(Board).filter(Board.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if board.owner_id == user.id:
        return True
    membership = db.query(BoardMember).filter(
        BoardMember.board_id == board_id,
        BoardMember.user_id == user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied")
    if require_admin and not membership.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return True
@app.on_event("startup")
async def startup_event():
    init_db()
@app.post("/auth/register", response_model=Token)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    if user.email:
        db_email = db.query(User).filter(User.email == user.email).first()
        if db_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    from middleware.auth import get_password_hash
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    access_token = create_access_token(data={"sub": db_user.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(data={"sub": db_user.username}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    from middleware.auth import authenticate_user
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(data={"sub": user.username}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
@app.post("/auth/refresh", response_model=Token)
async def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    payload = verify_token(token_data.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    new_access_token = create_access_token(data={"sub": user.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    new_refresh_token = rotate_refresh_token(token_data.refresh_token, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    return {"access_token": new_access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}
@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
@app.put("/users/me", response_model=UserResponse)
async def update_user_me(user_update: UserUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if user_update.username and user_update.username != current_user.username:
        existing = db.query(User).filter(User.username == user_update.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        current_user.username = user_update.username
    if user_update.email is not None:
        existing = db.query(User).filter(User.email == user_update.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already taken")
        current_user.email = user_update.email
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    db.commit()
    db.refresh(current_user)
    return current_user
@app.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db.delete(current_user)
    db.commit()
    return None
@app.get("/boards", response_model=List[BoardResponse])
async def get_user_boards(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    owned_boards = db.query(Board).filter(Board.owner_id == current_user.id).all()
    member_boards = db.query(Board).join(BoardMember).filter(
        BoardMember.user_id == current_user.id
    ).all()
    all_boards = list(set(owned_boards + member_boards))
    return all_boards
@app.post("/boards", response_model=BoardResponse)
async def create_board(
    board: BoardCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_board = Board(name=board.name, description=board.description, owner_id=current_user.id)
    db.add(db_board)
    db.commit()
    db.refresh(db_board)
    return db_board
@app.get("/boards/{board_id}", response_model=BoardResponse)
async def get_board(
    board_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    check_board_permission(board_id, current_user, db)
    board = db.query(Board).filter(Board.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board
@app.put("/boards/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: int,
    board_update: BoardUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    check_board_permission(board_id, current_user, db, require_admin=True)
    board = db.query(Board).filter(Board.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if board_update.name is not None:
        board.name = board_update.name
    if board_update.description is not None:
        board.description = board_update.description
    db.commit()
    db.refresh(board)
    await manager.broadcast({"type": "board_updated", "board_id": board_id}, str(board_id))
    return board
@app.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    board = db.query(Board).filter(Board.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if board.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only board owner can delete the board")
    await manager.broadcast({"type": "board_deleted", "board_id": board_id}, str(board_id))
    db.query(List).filter(List.board_id == board_id).delete()
    db.query(BoardMember).filter(BoardMember.board_id == board_id).delete()
    db.delete(board)
    db.commit()
    return None
@app.post("/boards/{board_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_board_member(
    board_id: int,
    member_data: BoardMemberAdd,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    check_board_permission(board_id, current_user, db, require_admin=True)
    user_to_add = db.query(User).filter(User.username == member_data.username).first()
    if not user_to_add:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(BoardMember).filter(
        BoardMember.board_id == board_id,
        BoardMember.user_id == user_to_add.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already a member")
    member = BoardMember(board_id=board_id, user_id=user_to_add.id, is_admin=member_data.is_admin)
    db.add(member)
    db.commit()
    await manager.broadcast({"type": "member_added", "board_id": board_id, "user_id": user_to_add.id}, str(board_id))
    return None
@app.delete("/boards/{board_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_board_member(
    board_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    check_board_permission(board_id, current_user, db, require_admin=True)
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    board = db.query(Board).filter(Board.id == board_id).first()
    if board and board.owner_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove board owner")
    member = db.query(BoardMember).filter(
        BoardMember.board_id == board_id,
        BoardMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
    await manager.broadcast({"type": "member_removed", "board_id": board_id, "user_id": user_id}, str(board_id))
    return None
@app.get("/boards/{board_id}/lists", response_model=List[ListResponse])
async def get_board_lists(
    board_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    check_board_permission(board_id, current_user, db)
    lists = db.query(List).filter(List.board_id == board_id).order_by(List.position).all()
    return lists
@app.post("/boards/{board_id}/lists", response_model=ListResponse)
async def create_list(
    board_id: int,
    list_data: ListCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    check_board_permission(board_id, current_user, db)
    max_position = db.query(List).filter(List.board_id == board_id).count()
    db_list = List(
        name=list_data.name,
        board_id=board_id,
        position=list_data.position if list_data.position is not None else max_position
    )
    db.add(db_list)
    db.commit()
    db.refresh(db_list)
    await manager.broadcast({"type": "list_created", "board_id": board_id, "list": db_list.id}, str(board_id))
    return db_list
@app.get("/lists/{list_id}", response_model=ListResponse)
async def get_list(
    list_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    list_item = db.query(List).filter(List.id == list_id).first()
    if not list_item:
        raise HTTPException(status_code=404, detail="List not found")
    check_board_permission(list_item.board_id, current_user, db)
    return list_item
@app.put("/lists/{list_id}", response_model=ListResponse)
async def update_list(
    list_id: int,
    list_update: ListUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    list_item = db.query(List).filter(List.id == list_id).first()
    if not list_item:
        raise HTTPException(status_code=404, detail="List not found")
    check_board_permission(list_item.board_id, current_user, db)
    if list_update.name is not None:
        list_item.name = list_update.name
    if list_update.position is not None:
        list_item.position = list_update.position
    db.commit()
    db.refresh(list_item)
    await manager.broadcast({"type": "list_updated", "list_id": list_id}, str(list_item.board_id))
    return list_item
@app.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_list(
    list_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    list_item = db.query(List).filter(List.id == list_id).first()
    if not list_item:
        raise HTTPException(status_code=404, detail="List not found")
    check_board_permission(list_item.board_id, current_user, db, require_admin=True)
    board_id = list_item.board_id
    await manager.broadcast({"type": "list_deleted", "list_id": list_id}, str(board_id))
    db.query(Card).filter(Card.list_id == list_id).delete()
    db.delete(list_item)
    db.commit()
    return None
@app.post("/lists/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_lists(
    reorder_data: list = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not reorder_data or len(reorder_data) == 0:
        raise HTTPException(status_code=400, detail="No lists to reorder")
    board_id = None
    for item in reorder_data:
        list_item = db.query(List).filter(List.id == item['id']).first()
        if not list_item:
            raise HTTPException(status_code=404, detail=f"List {item['id']} not found")
        if board_id is None:
            board_id = list_item.board_id
        elif list_item.board_id != board_id:
            raise HTTPException(status_code=400, detail="All lists must belong to the same board")
        check_board_permission(list_item.board_id, current_user, db)
    for item in reorder_data:
        db.query(List).filter(List.id == item['id']).update({"position": item['position']})
    db.commit()
    await manager.broadcast({"type": "lists_reordered", "board_id": board_id}, str(board_id))
    return None
@app.get("/lists/{list_id}/cards", response_model=List[CardResponse])
async def get_list_cards(
    list_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    list_item = db.query(List).filter(List.id == list_id).first()
    if not list_item:
        raise HTTPException(status_code=404, detail="List not found")
    check_board_permission(list_item.board_id, current_user, db)
    cards = db.query(Card).filter(Card.list_id == list_id).order_by(Card.position).all()
    return cards
@app.post("/lists/{list_id}/cards", response_model=CardResponse)
async def create_card(
    list_id: int,
    card_data: CardCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    list_item = db.query(List).filter(List.id == list_id).first()
    if not list_item:
        raise HTTPException(status_code=404, detail="List not found")
    check_board_permission(list_item.board_id, current_user, db)
    max_position = db.query(Card).filter(Card.list_id == list_id).count()
    db_card = Card(
        title=card_data.title,
        description=card_data.description,
        list_id=list_id,
        position=card_data.position if card_data.position is not None else max_position,
        assigned_to=card_data.assigned_to,
        due_date=card_data.due_date
    )
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    await manager.broadcast({"type": "card_created", "list_id": list_id, "card": db_card.id}, str(list_item.board_id))
    return db_card
@app.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    check_board_permission(list_item.board_id, current_user, db)
    return card
@app.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: int,
    card_update: CardUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    check_board_permission(list_item.board_id, current_user, db)
    if card_update.title is not None:
        card.title = card_update.title
    if card_update.description is not None:
        card.description = card_update.description
    if card_update.position is not None:
        card.position = card_update.position
    if card_update.assigned_to is not None:
        card.assigned_to = card_update.assigned_to
    if card_update.due_date is not None:
        card.due_date = card_update.due_date
    db.commit()
    db.refresh(card)
    await manager.broadcast({"type": "card_updated", "card_id": card_id}, str(list_item.board_id))
    return card
@app.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    board_id = list_item.board_id
    check_board_permission(board_id, current_user, db)
    await manager.broadcast({"type": "card_deleted", "card_id": card_id}, str(board_id))
    db.delete(card)
    db.commit()
    return None
@app.post("/cards/{card_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_card(
    card_id: int,
    move_data: CardMove,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    check_board_permission(list_item.board_id, current_user, db)
    new_list = db.query(List).filter(List.id == move_data.new_list_id).first()
    if not new_list:
        raise HTTPException(status_code=404, detail="Target list not found")
    check_board_permission(new_list.board_id, current_user, db)
    if new_list.board_id != list_item.board_id:
        raise HTTPException(status_code=400, detail="Target list must belong to the same board")
    card.list_id = move_data.new_list_id
    card.position = move_data.new_position
    db.commit()
    await manager.broadcast({
        "type": "card_moved",
        "card_id": card_id,
        "new_list_id": move_data.new_list_id,
        "new_position": move_data.new_position
    }, str(list_item.board_id))
    return None
@app.post("/lists/{list_id}/cards/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_cards(
    list_id: int,
    reorder_data: list = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    list_item = db.query(List).filter(List.id == list_id).first()
    if not list_item:
        raise HTTPException(status_code=404, detail="List not found")
    check_board_permission(list_item.board_id, current_user, db)
    for item in reorder_data:
        card = db.query(Card).filter(Card.id == item['id']).first()
        if not card:
            raise HTTPException(status_code=404, detail=f"Card {item['id']} not found")
        if card.list_id != list_id:
            raise HTTPException(status_code=400, detail=f"Card {item['id']} does not belong to this list")
    for item in reorder_data:
        db.query(Card).filter(Card.id == item['id']).update({"position": item['position']})
    db.commit()
    await manager.broadcast({"type": "cards_reordered", "list_id": list_id}, str(list_item.board_id))
    return None
@app.get("/cards/{card_id}/labels", response_model=List[LabelResponse])
async def get_card_labels(
    card_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    check_board_permission(list_item.board_id, current_user, db)
    return card.labels
@app.post("/cards/{card_id}/labels", response_model=LabelResponse)
async def add_label_to_card(
    card_id: int,
    label_data: LabelCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    board_id = list_item.board_id
    check_board_permission(board_id, current_user, db)
    label = db.query(Label).filter(
        Label.name == label_data.name,
        Label.color == label_data.color,
        Label.board_id == board_id
    ).first()
    if not label:
        label = Label(name=label_data.name, color=label_data.color, board_id=board_id)
        db.add(label)
        db.commit()
        db.refresh(label)
    if label not in card.labels:
        card.labels.append(label)
        db.commit()
    await manager.broadcast({"type": "label_added_to_card", "card_id": card_id, "label": label.id}, str(board_id))
    return label
@app.delete("/cards/{card_id}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_label_from_card(
    card_id: int,
    label_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    board_id = list_item.board_id
    check_board_permission(board_id, current_user, db)
    label = db.query(Label).filter(Label.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    if label in card.labels:
        card.labels.remove(label)
        db.commit()
    await manager.broadcast({"type": "label_removed_from_card", "card_id": card_id, "label": label_id}, str(board_id))
    return None
@app.get("/cards/{card_id}/comments", response_model=List[CommentResponse])
async def get_card_comments(
    card_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    check_board_permission(list_item.board_id, current_user, db)
    comments = db.query(Comment).filter(Comment.card_id == card_id).order_by(Comment.created_at.desc()).all()
    return comments
@app.post("/cards/{card_id}/comments", response_model=CommentResponse)
async def create_comment(
    card_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    list_item = db.query(List).filter(List.id == card.list_id).first()
    board_id = list_item.board_id
    check_board_permission(board_id, current_user, db)
    comment = Comment(content=comment_data.content, card_id=card_id, author_id=current_user.id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    comment.author = current_user
    await manager.broadcast({"type": "comment_created", "card_id": card_id, "comment": comment.id}, str(board_id))
    return comment
@app.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    card = db.query(Card).filter(Card.id == comment.card_id).first()
    list_item = db.query(List).filter(List.id == card.list_id).first()
    board_id = list_item.board_id
    check_board_permission(board_id, current_user, db)
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")
    comment.content = comment_update.content
    db.commit()
    db.refresh(comment)
    await manager.broadcast({"type": "comment_updated", "comment_id": comment_id}, str(board_id))
    return comment
@app.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    card = db.query(Card).filter(Card.id == comment.card_id).first()
    list_item = db.query(List).filter(List.id == card.list_id).first()
    board_id = list_item.board_id
    check_board_permission(board_id, current_user, db)
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")
    await manager.broadcast({"type": "comment_deleted", "comment_id": comment_id}, str(board_id))
    db.delete(comment)
    db.commit()
    return None
@app.websocket("/ws/boards/{board_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    board_id: str,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    payload = verify_token(token, token_type="access")
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        check_board_permission(int(board_id), user, db)
    except:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect(websocket, board_id)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.broadcast(data, board_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, board_id)
app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = f"dist/{full_path}"
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse("dist/index.html")