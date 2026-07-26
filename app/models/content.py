from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Enum, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base