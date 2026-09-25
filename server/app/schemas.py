"""Pydantic request/response schemas — mirrors the real API contract (all 39 base
endpoints + Fix-Plan additions)."""
from __future__ import annotations
from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

Model = BaseModel
model_config_from_attrs = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth
class OtpRequestIn(Model):
    phone: str
    device_info: str | None = None


class OtpRequestOut(Model):
    sent: bool = True
    debug_otp: str | None = None  # non-prod only, dummy provider


class UserOut(Model):
    model_config = model_config_from_attrs
    id: str
    phone: str
    org_id: str | None
    role: str
    is_active: bool
    mfa_enabled: bool


class OtpVerifyIn(Model):
    phone: str
    otp: str
    device_info: str | None = None


class TokenOut(Model):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_token: str | None = None
    user: UserOut | None = None


class RefreshIn(Model):
    refresh_token: str


class LogoutIn(Model):
    refresh_token: str | None = None


class MfaEnrollOut(Model):
    secret: str
    otpauth_uri: str


class MfaConfirmIn(Model):
    code: str


class MfaChallengeIn(Model):
    mfa_token: str
    code: str


class SessionOut(Model):
    model_config = model_config_from_attrs
    id: str
    device_info: str | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


# ---------------------------------------------------------------- orgs
class OrgCreate(Model):
    name: str = Field(min_length=2, max_length=255)
    org_type: Literal["manufacturer", "regional_agent", "distributor_authorized",
                      "distributor_sub", "retailer", "transporter", "social_seller"]
    categories: list[str] = Field(default_factory=lambda: ["pharma"])


class OrgOut(Model):
    model_config = model_config_from_attrs
    id: str
    name: str
    org_type: str
    approval_status: str
    rejection_reason: str | None = None
    categories: list[str] = []
    notif_channels: list[str] = []
    notif_language: str = "en"
    webhook_secret: str | None = None  # only for org_admin callers
    created_at: datetime


class NotificationSettings(Model):
    channels: list[str] = Field(default_factory=lambda: ["push"])
    language: str = "en"


class KycDocOut(Model):
    model_config = model_config_from_attrs
    id: str
    org_id: str
    document_type: str
    file_url: str
    status: str
    uploaded_at: datetime


class UserInviteIn(Model):
    phone: str
    role: Literal["org_admin", "member"] = "member"


class UserPatch(Model):
    role: Literal["org_admin", "member"] | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------- network
class InviteCreate(Model):
    product_code: str | None = None
    authorized: bool = True
    expires_in_days: int | None = 30


class InviteOut(Model):
    model_config = model_config_from_attrs
    code: str
    created_by_org_id: str
    manufacturer_org_id: str
    product_code: str | None
    authorized: bool
    expires_at: datetime | None
    used_by_org_id: str | None


class TreeNode(Model):
    org_id: str
    name: str
    org_type: str


class TreeEdge(Model):
    from_org_id: str
    to_org_id: str
    product_code: str | None
    authorized: bool


class TreeOut(Model):
    manufacturer_org_id: str | None
    nodes: list[TreeNode] = []
    edges: list[TreeEdge] = []


# ---------------------------------------------------------------- products & batches
class ProductCreate(Model):
    product_code: str
    name: str
    category: str = "pharma"


class ProductOut(Model):
    model_config = model_config_from_attrs
    id: str
    org_id: str
    product_code: str
    name: str
    category: str
    created_at: datetime


class BatchCreate(Model):
    product_id: str
    batch_number: str
    quantity: int = Field(gt=0, le=1_000_000)
    mfg_date: date | None = None
    expiry_date: date | None = None


class BatchOut(Model):
    model_config = model_config_from_attrs
    id: str
    product_id: str
    org_id: str
    batch_number: str
    quantity: int
    mfg_date: date | None
    expiry_date: date | None
    recalled: bool
    recall_reason: str | None = None
    units_generated: int = 0
    created_at: datetime


class UnitsGenerateIn(Model):
    count: int | None = Field(default=None, gt=0, le=100_000)


class UnitsGeneratedOut(Model):
    unit_ids: list[str]


class RecallIn(Model):
    reason: str = Field(min_length=3)


class RecallOut(Model):
    recalled: bool = True
    affected_units: int
    affected_orgs_notified: int


class ExportLabelsIn(Model):
    format: Literal["csv", "pdf_sheet", "zpl"] = "csv"
    size_mm: float = Field(default=30.0, gt=5, le=150)


class BatchLookupOut(Model):
    batch: BatchOut
    product: ProductOut
    units_generated: int


# ---------------------------------------------------------------- units & verify
class UnitOut(Model):
    model_config = model_config_from_attrs
    id: str
    batch_id: str
    product_id: str
    current_state: str
    holder_org_id: str | None
    verify_count: int
    last_verified_at: datetime | None
    created_at: datetime


class VerifyEventOut(Model):
    event_type: str
    actor_org_id: str | None
    timestamp: datetime
    resulting_state: str | None


class DisclosureItemOut(Model):
    field_key: str
    label: str
    value: str


class VerifyOut(Model):
    status: Literal["genuine", "not_yet_in_circulation", "flagged", "recalled"]
    unit_id: str
    product_code: str | None = None
    product_name: str | None = None
    batch_number: str | None = None
    flag_reason: str | None = None
    disclosures: list[DisclosureItemOut] = []
    last_events: list[VerifyEventOut] = []


# ---------------------------------------------------------------- containers
class ContainerCreate(Model):
    container_type: Literal["box", "pallet", "shipment"] = "box"
    child_unit_ids: list[str] = Field(default_factory=list)
    child_container_ids: list[str] = Field(default_factory=list)


class ContainerChildOut(Model):
    child_type: str
    child_id: str
    state: str | None = None


class ContainerOut(Model):
    model_config = model_config_from_attrs
    id: str
    container_type: str
    holder_org_id: str | None
    state: str
    disaggregated: bool
    parent_container_id: str | None
    children: list[ContainerChildOut] = []
    created_at: datetime


class AddChildrenIn(Model):
    unit_ids: list[str] = Field(default_factory=list)
    container_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- events
class EventCreate(Model):
    client_event_id: str = Field(min_length=8, max_length=128)
    target_type: Literal["unit", "container"]
    target_id: str
    event_type: Literal["DISPATCH", "RECEIVE", "SALE", "RETURN", "FLAG", "UNFLAG"]
    gps_lat: float | None = Field(default=None, ge=-90, le=90)
    gps_lng: float | None = Field(default=None, ge=-180, le=180)


class EventOut(Model):
    model_config = model_config_from_attrs
    id: str
    client_event_id: str
    target_type: str
    target_id: str
    event_type: str
    actor_org_id: str | None
    actor_user_id: str | None
    gps_lat: float | None
    gps_lng: float | None
    resulting_state: str | None
    created_at: datetime


# ---------------------------------------------------------------- alerts
class AlertOut(Model):
    model_config = model_config_from_attrs
    id: str
    org_id: str
    target_type: str
    target_id: str
    reason: str
    severity: str
    status: str
    detail: str | None
    created_at: datetime


class AlertPatch(Model):
    status: Literal["reviewed"]


# ---------------------------------------------------------------- social
class SocialCreate(Model):
    platform: Literal["instagram", "whatsapp", "other"] = "other"
    post_url: str
    unit_ids: list[str] = Field(min_length=1)


class SocialOut(Model):
    model_config = model_config_from_attrs
    id: str
    org_id: str
    platform: str
    post_url: str
    unit_ids: list[str]
    created_at: datetime


# ---------------------------------------------------------------- admin
class AdminOrgOut(OrgOut):
    kyc_documents: list[KycDocOut] = []


class RejectIn(Model):
    reason: str = Field(min_length=3)


class FraudPatternsOut(Model):
    top_flag_reasons: list[dict[str, Any]] = []
    by_severity: list[dict[str, Any]] = []
    by_day: list[dict[str, Any]] = []


class RegulatorGrantCreate(Model):
    regulator_user_id: str
    batch_id: str
    expires_in_hours: int = Field(default=72, gt=0, le=24 * 90)
    reason: str = Field(min_length=3)


class RegulatorGrantOut(Model):
    model_config = model_config_from_attrs
    id: str
    regulator_user_id: str
    batch_id: str
    reason: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------- disclosures
class DisclosureFieldOut(Model):
    model_config = model_config_from_attrs
    id: str
    category: str
    field_key: str
    label: str
    field_type: str
    required: bool
    display_order: int


class DisclosureFieldCreate(Model):
    category: str
    field_key: str
    label: str
    field_type: Literal["text", "date", "multiline", "list"] = "text"
    required: bool = True
    display_order: int = 0


class DisclosuresPut(Model):
    values: dict[str, str]


class KycReqOut(Model):
    model_config = model_config_from_attrs
    id: str
    category: str
    document_type: str
    label: str
    required: bool


class KycReqCreate(Model):
    category: str
    document_type: str
    label: str
    required: bool = True


# ---------------------------------------------------------------- transfer exceptions
class TransferExceptionCreate(Model):
    recipient_org_id: str
    reason: str = Field(min_length=3)
    expires_in_hours: int = Field(default=72, gt=0, le=24 * 30)


class TransferExceptionOut(Model):
    model_config = model_config_from_attrs
    id: str
    target_type: str
    target_id: str
    granted_by_org_id: str
    recipient_org_id: str
    reason: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------- integrations
class TransporterWebhookIn(Model):
    action: Literal["pickup", "delivery"]
    target_type: Literal["unit", "container"] = "unit"
    target_ids: list[str] = Field(min_length=1, max_length=500)
    gps_lat: float | None = None
    gps_lng: float | None = None


class ListingLinkCreate(Model):
    channel: str
    sku: str
    unit_ids: list[str] = Field(min_length=1)


class ListingLinkOut(Model):
    model_config = model_config_from_attrs
    id: str
    org_id: str
    channel: str
    sku: str
    reserved_unit_ids: list[str]
    consumed_unit_ids: list[str]


class EcommerceWebhookIn(Model):
    channel: str
    sku: str
    gps_lat: float | None = None
    gps_lng: float | None = None
