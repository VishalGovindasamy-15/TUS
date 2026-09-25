"""SQLAlchemy models — portable across PostgreSQL (prod) and SQLite (tests).

String PKs + generic JSON columns keep the same schema working on both backends.
String columns are used instead of native DB enums for the same reason; the allowed
values live in the StrEnum classes below and are validated at the API boundary.
"""
from __future__ import annotations
import enum
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import uid
from app.core.time import utcnow
from app.db import Base


# ---------------------------------------------------------------- enums (app-level)
class OrgType(str, enum.Enum):
    manufacturer = "manufacturer"
    regional_agent = "regional_agent"
    distributor_authorized = "distributor_authorized"
    distributor_sub = "distributor_sub"
    retailer = "retailer"
    transporter = "transporter"
    social_seller = "social_seller"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class UserRole(str, enum.Enum):
    platform_admin = "platform_admin"
    org_admin = "org_admin"
    member = "member"


class UnitState(str, enum.Enum):
    ISSUED = "ISSUED"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    SOLD = "SOLD"
    RETURNED = "RETURNED"
    FLAGGED = "FLAGGED"


class EventType(str, enum.Enum):
    DISPATCH = "DISPATCH"
    RECEIVE = "RECEIVE"
    SALE = "SALE"
    RETURN = "RETURN"
    FLAG = "FLAG"
    UNFLAG = "UNFLAG"


class ContainerType(str, enum.Enum):
    box = "box"
    pallet = "pallet"
    shipment = "shipment"


INVITE_CAPABLE_ORG_TYPES = {
    OrgType.manufacturer.value,
    OrgType.regional_agent.value,
    OrgType.distributor_authorized.value,
}


# ---------------------------------------------------------------- orgs & users
class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("org"))
    name: Mapped[str] = mapped_column(String(255))
    org_type: Mapped[str] = mapped_column(String(64), index=True)
    approval_status: Mapped[str] = mapped_column(String(32), default=ApprovalStatus.pending.value, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["pharma", "auto_parts"]
    notif_channels: Mapped[list] = mapped_column(JSON, default=lambda: ["push"])
    notif_language: Mapped[str] = mapped_column(String(16), default="en")
    webhook_secret: Mapped[str] = mapped_column(String(128), default=lambda: uid("whsec"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("usr"))
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    org_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("orgs.id"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.member.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # jti
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(128), index=True)
    device_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("otp"))
    phone: Mapped[str] = mapped_column(String(32), index=True)
    otp_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- catalogue
class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("prd"))
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), default="pharma", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_products_org_code", "org_id", "product_code", unique=True),)


class DisclosureFieldDefinition(Base):
    __tablename__ = "disclosure_field_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("fld"))
    category: Mapped[str] = mapped_column(String(64), index=True)
    field_key: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(255))
    field_type: Mapped[str] = mapped_column(String(32), default="text")  # text|date|multiline|list
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_disclosure_cat_key", "category", "field_key", unique=True),)


class ProductDisclosure(Base):
    __tablename__ = "product_disclosures"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("dis"))
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("products.id"), index=True)
    field_id: Mapped[str] = mapped_column(String(64), ForeignKey("disclosure_field_definitions.id"))
    value: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (Index("ix_disclosure_prod_field", "product_id", "field_id", unique=True),)


class KycRequirement(Base):
    __tablename__ = "kyc_requirements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("kyc"))
    category: Mapped[str] = mapped_column(String(64), index=True)
    document_type: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(255))
    required: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_kyc_cat_type", "category", "document_type", unique=True),)


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("doc"))
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(128))
    file_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- batches & units
class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("bat"))
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("products.id"), index=True)
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    batch_number: Mapped[str] = mapped_column(String(128), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    mfg_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recalled: Mapped[bool] = mapped_column(Boolean, default=False)
    recall_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_batches_prod_number", "product_id", "batch_number", unique=True),)


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # the unit_id in QRs
    batch_id: Mapped[str] = mapped_column(String(64), ForeignKey("batches.id"), index=True)
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("products.id"), index=True)
    current_state: Mapped[str] = mapped_column(String(32), default=UnitState.ISSUED.value, index=True)
    holder_org_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("orgs.id"), nullable=True, index=True)
    verify_count: Mapped[int] = mapped_column(Integer, default=0)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VerifySignal(Base):
    """Anonymous coarse-location breadcrumbs for the multi_location_verify rule.

    No IP, device ID, or personal data — only a ~11km grid cell + timestamp.
    """

    __tablename__ = "verify_signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("vrf"))
    unit_id: Mapped[str] = mapped_column(String(64), ForeignKey("units.id"), index=True)
    grid_lat: Mapped[float] = mapped_column(Float)
    grid_lng: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_verify_signals_unit_time", "unit_id", "created_at"),)


# ---------------------------------------------------------------- network
class NetworkInvite(Base):
    __tablename__ = "network_invites"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_by_org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    manufacturer_org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    product_code: Mapped[str | None] = mapped_column(String(128), nullable=True)  # None = all products
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_org_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NetworkEdge(Base):
    __tablename__ = "network_edges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("edg"))
    manufacturer_org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    partner_org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    product_code: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TransferException(Base):
    __tablename__ = "transfer_exceptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("exc"))
    target_type: Mapped[str] = mapped_column(String(32))  # unit | container
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    granted_by_org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"))
    recipient_org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- containers
class Container(Base):
    __tablename__ = "containers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("ctr"))
    container_type: Mapped[str] = mapped_column(String(32))  # box | pallet | shipment
    created_by_org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    holder_org_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("orgs.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default=UnitState.ISSUED.value)
    disaggregated: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_container_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("containers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContainerItem(Base):
    __tablename__ = "container_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("cit"))
    container_id: Mapped[str] = mapped_column(String(64), ForeignKey("containers.id"), index=True)
    child_type: Mapped[str] = mapped_column(String(32))  # unit | container
    child_id: Mapped[str] = mapped_column(String(64), index=True)


# ---------------------------------------------------------------- events & alerts
class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("evt"))
    client_event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    target_type: Mapped[str] = mapped_column(String(32), index=True)  # unit | container
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    actor_org_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("orgs.id"), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    resulting_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    __table_args__ = (Index("ix_events_target_time", "target_id", "created_at"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("alr"))
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)  # low | medium | high
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | reviewed
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# ---------------------------------------------------------------- social / admin / integrations
class SocialListing(Base):
    __tablename__ = "social_listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("soc"))
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    platform: Mapped[str] = mapped_column(String(64))
    post_url: Mapped[str] = mapped_column(Text)
    unit_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatorGrant(Base):
    __tablename__ = "regulator_grants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("reg"))
    regulator_user_id: Mapped[str] = mapped_column(String(128), index=True)
    batch_id: Mapped[str] = mapped_column(String(64), ForeignKey("batches.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductListingLink(Base):
    """E-commerce SKU -> pool of unit_ids reserved for that channel (Fix Plan 9.2)."""

    __tablename__ = "product_listing_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uid("lnk"))
    org_id: Mapped[str] = mapped_column(String(64), ForeignKey("orgs.id"), index=True)
    channel: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str] = mapped_column(String(128))
    reserved_unit_ids: Mapped[list] = mapped_column(JSON, default=list)
    consumed_unit_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_listing_org_channel_sku", "org_id", "channel", "sku", unique=True),)
