from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, Date, Boolean, Table, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
class Base(DeclarativeBase):
    pass
board_members_table = Table(
    'board_members',
    Base.metadata,
    Column('board_id', Integer, ForeignKey('boards.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Index('idx_board_members_board_id', 'board_id'),
    Index('idx_board_members_user_id', 'user_id'),
)
card_assignees_table = Table(
    'card_assignees',
    Base.metadata,
    Column('card_id', Integer, ForeignKey('cards.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Index('idx_card_assignees_card_id', 'card_id'),
    Index('idx_card_assignees_user_id', 'user_id'),
)
card_labels_table = Table(
    'card_labels',
    Base.metadata,
    Column('card_id', Integer, ForeignKey('cards.id', ondelete='CASCADE'), primary_key=True),
    Column('label_id', Integer, ForeignKey('labels.id', ondelete='CASCADE'), primary_key=True),
    Index('idx_card_labels_card_id', 'card_id'),
    Index('idx_card_labels_label_id', 'label_id'),
)
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    owned_boards: Mapped[list["Board"]] = relationship("Board", back_populates="owner", cascade="all, delete-orphan", foreign_keys="[Board.owner_id]")
    member_boards: Mapped[list["Board"]] = relationship("Board", secondary=board_members_table, back_populates="members")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    assigned_cards: Mapped[list["Card"]] = relationship("Card", secondary=card_assignees_table, back_populates="assignees")
class Board(Base):
    __tablename__ = 'boards'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    owner: Mapped["User"] = relationship("User", back_populates="owned_boards", foreign_keys=[owner_id])
    lists: Mapped[list["List"]] = relationship("List", back_populates="board", cascade="all, delete-orphan")
    members: Mapped[list["User"]] = relationship("User", secondary=board_members_table, back_populates="member_boards")
    labels: Mapped[list["Label"]] = relationship("Label", back_populates="board", cascade="all, delete-orphan")
class List(Base):
    __tablename__ = 'lists'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey('boards.id', ondelete='CASCADE'), nullable=False, index=True)
    board: Mapped["Board"] = relationship("Board", back_populates="lists", foreign_keys=[board_id])
    cards: Mapped[list["Card"]] = relationship("Card", back_populates="list", cascade="all, delete-orphan")
class Card(Base):
    __tablename__ = 'cards'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey('lists.id', ondelete='CASCADE'), nullable=False, index=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey('boards.id', ondelete='CASCADE'), nullable=False, index=True)
    list: Mapped["List"] = relationship("List", back_populates="cards", foreign_keys=[list_id])
    board: Mapped["Board"] = relationship("Board", foreign_keys=[board_id])
    labels: Mapped[list["Label"]] = relationship("Label", secondary=card_labels_table, back_populates="cards")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="card", cascade="all, delete-orphan")
    assignees: Mapped[list["User"]] = relationship("User", secondary=card_assignees_table, back_populates="assigned_cards")
class Label(Base):
    __tablename__ = 'labels'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey('boards.id', ondelete='CASCADE'), nullable=False, index=True)
    board: Mapped["Board"] = relationship("Board", back_populates="labels", foreign_keys=[board_id])
    cards: Mapped[list["Card"]] = relationship("Card", secondary=card_labels_table, back_populates="labels")
class Comment(Base):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey('cards.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    card: Mapped["Card"] = relationship("Card", back_populates="comments", foreign_keys=[card_id])
    user: Mapped["User"] = relationship("User", back_populates="comments", foreign_keys=[user_id])