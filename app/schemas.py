from pydantic import BaseModel, field_validator
from typing import Optional, List, Literal
from decimal import Decimal
from datetime import datetime, date as date_type


# =============================================
# КАТЕГОРИИ
# =============================================

class CategoryBase(BaseModel):
    name: str
    Category_id: Optional[int] = None
    packaging_unit_name: Optional[str] = None
    sort_order: Optional[int] = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    Category_id: Optional[int] = None
    packaging_unit_name: Optional[str] = None
    sort_order: Optional[int] = None


class Category(CategoryBase):
    id: int

    class Config:
        from_attributes = True


# =============================================
# ТОВАРЫ
# =============================================

class ProductBase(BaseModel):
    name: str
    price: Decimal
    brand: Optional[str] = None
    description: Optional[str] = None
    packaging_unit_value: Optional[Decimal] = None
    sort_order: Optional[int] = 0


class ProductCreate(ProductBase):
    Category_id: int


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    Category_id: Optional[int] = None
    price: Optional[Decimal] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    packaging_unit_value: Optional[Decimal] = None
    sort_order: Optional[int] = None


class Product(ProductBase):
    id: int
    Category_id: int

    class Config:
        from_attributes = True


# =============================================
# ВСПОМОГАТЕЛЬНЫЕ СХЕМЫ ДЕРЕВА
# =============================================

class DescendantInfo(BaseModel):
    id: int
    name: str
    level: int
    is_product: bool
    product_id: Optional[int] = None
    sort_order: int


class ParentInfo(BaseModel):
    id: int
    name: str
    level: int


class TerminalProduct(BaseModel):
    product_id: int
    product_name: str
    price: Decimal
    brand: Optional[str]
    description: Optional[str]
    packaging_unit_value: Optional[Decimal]


class CycleCheckResult(BaseModel):
    cycle_found: bool
    cycle_path: str


class TreeNode(BaseModel):
    id: Optional[int]
    name: str
    type: str
    packaging_unit_name: Optional[str] = None
    price: Optional[float] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    packaging_unit_value: Optional[float] = None
    sort_order: Optional[int] = 0
    children: List['TreeNode'] = []


TreeNode.model_rebuild()


# =============================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================

class EnumClassBase(BaseModel):
    name: str
    description: Optional[str] = None


class EnumClassCreate(EnumClassBase):
    pass


class EnumClassUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class EnumClassResponse(EnumClassBase):
    id: int
    created_at: Optional[datetime] = None
    values_count: Optional[int] = None

    class Config:
        from_attributes = True


class EnumValueBase(BaseModel):
    value: str
    sort_order: Optional[int] = 0


class EnumValueCreate(EnumValueBase):
    pass


class EnumValueUpdate(BaseModel):
    value: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class EnumValueResponse(EnumValueBase):
    id: int
    enum_class_id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnumValueDetailResponse(BaseModel):
    id: int
    value: str
    class_name: str
    class_description: Optional[str] = None


class ReorderEnumValuesRequest(BaseModel):
    value_ids: List[int]


# =============================================
# ПАРАМЕТРЫ
# =============================================

class ParamDefinitionBase(BaseModel):
    name: str
    description: Optional[str] = None
    param_type: Literal["numeric", "enum"]
    unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    enum_class_id: Optional[int] = None
    is_required: Optional[bool] = False

    @field_validator("enum_class_id")
    @classmethod
    def check_enum_class(cls, v, info):
        if info.data.get("param_type") == "enum" and v is None:
            raise ValueError("enum_class_id is required for param_type='enum'")
        return v


class ParamDefinitionCreate(ParamDefinitionBase):
    pass


class ParamDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    is_required: Optional[bool] = None


class ParamDefinitionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    param_type: str
    unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    enum_class_id: Optional[int] = None
    enum_class_name: Optional[str] = None
    is_required: bool

    class Config:
        from_attributes = True


class CategoryParamCreate(BaseModel):
    param_id: int
    is_inherited: Optional[bool] = True
    sort_order: Optional[int] = 0


class CategoryParamUpdate(BaseModel):
    is_inherited: Optional[bool] = None
    sort_order: Optional[int] = None


class CategoryParamResponse(BaseModel):
    id: int
    category_id: int
    param_id: int
    param_name: str
    param_type: str
    unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    enum_class_id: Optional[int] = None
    is_required: bool
    is_inherited: bool
    sort_order: int

    class Config:
        from_attributes = True


class InheritedParamResponse(BaseModel):
    param_id: int
    param_name: str
    description: Optional[str] = None
    param_type: str
    unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    enum_class_id: Optional[int] = None
    enum_class_name: Optional[str] = None
    is_required: bool
    is_inherited: bool
    source_category_id: int
    source_category_name: str
    sort_order: int


class ProductParamNumericSet(BaseModel):
    param_id: int
    value: Decimal


class ProductParamEnumSet(BaseModel):
    param_id: int
    enum_value_id: int


class ProductParamResponse(BaseModel):
    param_id: int
    param_name: str
    param_type: str
    unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    numeric_value: Optional[Decimal] = None
    enum_value_id: Optional[int] = None
    enum_value_text: Optional[str] = None
    is_required: bool


class ParamAggregateResponse(BaseModel):
    param_id: int
    param_name: str
    unit: Optional[str] = None
    count: int
    min_val: Optional[Decimal] = None
    max_val: Optional[Decimal] = None
    avg_val: Optional[Decimal] = None
    sum_val: Optional[Decimal] = None


class ProductSearchFilter(BaseModel):
    param_id: int
    num_min: Optional[Decimal] = None
    num_max: Optional[Decimal] = None
    enum_value_id: Optional[int] = None


class ProductSearchRequest(BaseModel):
    category_id: int
    filters: List[ProductSearchFilter]


class ProductSearchResult(BaseModel):
    product_id: int
    product_name: str
    category_id: int
    category_name: str
    price: Decimal
    brand: Optional[str] = None


# =============================================
# ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ (ХО)
# =============================================

class XOClassBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = 0


class XOClassCreate(XOClassBase):
    pass


class XOClassUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class XOClassResponse(XOClassBase):
    id: int
    instance_count: Optional[int] = 0

    class Config:
        from_attributes = True


class XOClassTreeNode(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int
    depth: int
    instance_count: int


class XOParamDefCreate(BaseModel):
    param_def_id: int
    is_inherited: Optional[bool] = True
    sort_order: Optional[int] = 0


class XOParamDefUpdate(BaseModel):
    is_inherited: Optional[bool] = None
    sort_order: Optional[int] = None


class XOParamDefResponse(BaseModel):
    param_def_id: int
    param_name: str
    param_type: str
    unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    enum_class_id: Optional[int] = None
    enum_class_name: Optional[str] = None
    is_required: bool
    is_inherited_xo: bool
    source_class_id: int
    source_class_name: str
    sort_order: int


class XORoleDefCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_required: Optional[bool] = True
    subject_type: Optional[str] = "any"


class XORoleDefUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_required: Optional[bool] = None
    subject_type: Optional[str] = None


class XORoleDefResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_required: bool
    subject_type: Optional[str] = None

    class Config:
        from_attributes = True


class XOInstanceCreate(BaseModel):
    xo_class_id: int
    number: Optional[str] = None
    op_date: Optional[date_type] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None


class XOInstanceUpdate(BaseModel):
    number: Optional[str] = None
    op_date: Optional[date_type] = None
    notes: Optional[str] = None


class XOInstanceResponse(BaseModel):
    id: int
    xo_class_id: int
    xo_class_name: Optional[str] = None
    number: Optional[str] = None
    op_date: date_type
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class XOParamValueSet(BaseModel):
    param_def_id: int
    numeric_value: Optional[Decimal] = None
    text_value: Optional[str] = None
    enum_value_id: Optional[int] = None


class XOParamValueResponse(BaseModel):
    param_def_id: int
    param_name: str
    param_type: str
    unit: Optional[str] = None
    numeric_value: Optional[Decimal] = None
    text_value: Optional[str] = None
    enum_value_id: Optional[int] = None
    enum_value_text: Optional[str] = None


class XORoleAssignCreate(BaseModel):
    role_def_id: int
    subject_name: str
    subject_id: Optional[int] = None
    subject_type: Optional[str] = None


class XORoleAssignResponse(BaseModel):
    role_def_id: int
    role_name: str
    is_required: bool
    subject_name: Optional[str] = None
    subject_type: Optional[str] = None
    subject_id: Optional[int] = None


class XOLineCreate(BaseModel):
    product_id: Optional[int] = None
    quantity: Decimal
    price: Optional[Decimal] = None
    unit_name: Optional[str] = None


class XOLineResponse(BaseModel):
    line_id: int
    line_order: int
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    quantity: Decimal
    price: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    unit_name: Optional[str] = None


class XOFullFieldResponse(BaseModel):
    field_type: str
    field_name: str
    field_value: Optional[str] = None


class XOSearchResult(BaseModel):
    xo_id: int
    xo_number: Optional[str] = None
    xo_class: str
    op_date: date_type
    status: str
    param_name: str
    param_value: Optional[str] = None


# =============================================
# ПОЛЬЗОВАТЕЛИ
# =============================================

class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================
# АУДИТ
# =============================================

class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    user_login: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================
# DASHBOARD / ANALYTICS
# =============================================

class DashboardStats(BaseModel):
    categories: int
    products: int
    params: int
    xo_instances: int


class CategoryDistribution(BaseModel):
    category_name: str
    product_count: int


class CategoryPriceAvg(BaseModel):
    category_name: str
    avg_price: float


class ParamUsage(BaseModel):
    param_name: str
    usage_count: int


class XOMonthly(BaseModel):
    month: str
    count: int


class AnalyticsResponse(BaseModel):
    category_distribution: List[CategoryDistribution]
    category_avg_price: List[CategoryPriceAvg]
    param_usage: List[ParamUsage]
    xo_monthly: List[XOMonthly]
