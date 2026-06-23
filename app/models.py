from sqlalchemy import Column, Integer, String, Numeric, Text, ForeignKey, DateTime, Boolean, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


# =============================================
# ПОЛЬЗОВАТЕЛИ (JWT-аутентификация)
# =============================================

class User(Base):
    __tablename__ = "app_user"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(20),  nullable=False,
                           default="user", server_default="user")
    is_active     = Column(Boolean, nullable=False,
                           default=True, server_default="true")
    created_at    = Column(DateTime, server_default=func.now())


# =============================================
# ЖУРНАЛ ИЗМЕНЕНИЙ (аудит)
# =============================================

class AuditLog(Base):
    __tablename__ = "audit_log"

    id          = Column(Integer, primary_key=True, index=True)
    timestamp   = Column(DateTime, server_default=func.now(), nullable=False)
    user_login  = Column(String(100), nullable=True)
    action      = Column(String(50),  nullable=False)
    entity_type = Column(String(50),  nullable=False)
    entity_id   = Column(Integer, nullable=True)
    details     = Column(Text, nullable=True)


# =============================================
# КАТЕГОРИИ И ТОВАРЫ
# =============================================

class Category(Base):
    __tablename__ = "category"

    id                 = Column(Integer, primary_key=True, index=True)
    Category_id        = Column(Integer, ForeignKey("category.id", ondelete="RESTRICT"), nullable=True)
    name               = Column(String(255), nullable=False)
    packaging_unit_name = Column(String(100))
    sort_order         = Column(Integer, default=0)

    parent        = relationship("Category", remote_side=[id], back_populates="children")
    children      = relationship("Category", back_populates="parent", cascade="all, delete-orphan")
    products      = relationship("Product", back_populates="category", cascade="all, delete-orphan")
    category_params = relationship("CategoryParam", back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "product"

    id                   = Column(Integer, primary_key=True, index=True)
    Category_id          = Column(Integer, ForeignKey("category.id", ondelete="RESTRICT"), nullable=False)
    name                 = Column(String(255), nullable=False)
    price                = Column(Numeric(10, 2), nullable=False)
    brand                = Column(String(200))
    description          = Column(Text)
    packaging_unit_value = Column(Numeric(10, 2))
    sort_order           = Column(Integer, default=0)

    enum_product_type_id = Column(Integer, ForeignKey("enum_value.id", ondelete="SET NULL"), nullable=True)
    enum_unit_id         = Column(Integer, ForeignKey("enum_value.id", ondelete="SET NULL"), nullable=True)
    enum_season_id       = Column(Integer, ForeignKey("enum_value.id", ondelete="SET NULL"), nullable=True)

    category         = relationship("Category", back_populates="products")
    enum_product_type = relationship("EnumValue", foreign_keys=[enum_product_type_id])
    enum_unit        = relationship("EnumValue", foreign_keys=[enum_unit_id])
    enum_season      = relationship("EnumValue", foreign_keys=[enum_season_id])

    numeric_params = relationship("ProductParamNumeric", back_populates="product", cascade="all, delete-orphan")
    enum_params    = relationship("ProductParamEnum",    back_populates="product", cascade="all, delete-orphan")
    xo_lines       = relationship("XOLine", back_populates="product")


# =============================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================

class EnumClass(Base):
    __tablename__ = "enum_class"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

    values           = relationship("EnumValue", back_populates="enum_class", cascade="all, delete-orphan")
    param_definitions = relationship("ParamDefinition", back_populates="enum_class")


class EnumValue(Base):
    __tablename__ = "enum_value"

    id            = Column(Integer, primary_key=True, index=True)
    enum_class_id = Column(Integer, ForeignKey("enum_class.id", ondelete="CASCADE"), nullable=False)
    value         = Column(String(255), nullable=False)
    sort_order    = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())

    enum_class         = relationship("EnumClass", back_populates="values")
    product_param_enums = relationship("ProductParamEnum", back_populates="enum_value")
    xo_param_values    = relationship("XOParamValue", back_populates="enum_value")


# =============================================
# СИСТЕМА НАСТРАИВАЕМЫХ ПАРАМЕТРОВ
# =============================================

class ParamDefinition(Base):
    __tablename__ = "param_definition"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    param_type  = Column(String(20), nullable=False)

    unit          = Column(String(50),    nullable=True)
    min_value     = Column(Numeric(15, 4), nullable=True)
    max_value     = Column(Numeric(15, 4), nullable=True)
    enum_class_id = Column(Integer, ForeignKey("enum_class.id", ondelete="SET NULL"), nullable=True)
    is_required   = Column(Boolean, default=False)
    created_at    = Column(DateTime, server_default=func.now())

    enum_class       = relationship("EnumClass", back_populates="param_definitions")
    category_params  = relationship("CategoryParam",       back_populates="param_definition", cascade="all, delete-orphan")
    numeric_values   = relationship("ProductParamNumeric", back_populates="param_definition", cascade="all, delete-orphan")
    enum_values_link = relationship("ProductParamEnum",    back_populates="param_definition", cascade="all, delete-orphan")
    xo_param_defs    = relationship("XOParamDef",  back_populates="param_definition", cascade="all, delete-orphan")
    xo_param_values  = relationship("XOParamValue", back_populates="param_definition", cascade="all, delete-orphan")


class CategoryParam(Base):
    __tablename__ = "category_param"

    id           = Column(Integer, primary_key=True, index=True)
    category_id  = Column(Integer, ForeignKey("category.id",        ondelete="CASCADE"), nullable=False)
    param_id     = Column(Integer, ForeignKey("param_definition.id", ondelete="CASCADE"), nullable=False)
    is_inherited = Column(Boolean, default=True)
    sort_order   = Column(Integer, default=0)

    category        = relationship("Category",        back_populates="category_params")
    param_definition = relationship("ParamDefinition", back_populates="category_params")


class ProductParamNumeric(Base):
    __tablename__ = "product_param_numeric"

    id         = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product.id",          ondelete="CASCADE"), nullable=False)
    param_id   = Column(Integer, ForeignKey("param_definition.id", ondelete="CASCADE"), nullable=False)
    value      = Column(Numeric(15, 4), nullable=False)

    product          = relationship("Product",         back_populates="numeric_params")
    param_definition = relationship("ParamDefinition", back_populates="numeric_values")


class ProductParamEnum(Base):
    __tablename__ = "product_param_enum"

    id            = Column(Integer, primary_key=True, index=True)
    product_id    = Column(Integer, ForeignKey("product.id",          ondelete="CASCADE"), nullable=False)
    param_id      = Column(Integer, ForeignKey("param_definition.id", ondelete="CASCADE"), nullable=False)
    enum_value_id = Column(Integer, ForeignKey("enum_value.id",       ondelete="CASCADE"), nullable=False)

    product          = relationship("Product",         back_populates="enum_params")
    param_definition = relationship("ParamDefinition", back_populates="enum_values_link")
    enum_value       = relationship("EnumValue",       back_populates="product_param_enums")


# =============================================
# ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ
# =============================================

class XOClass(Base):
    __tablename__ = "xo_class"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    parent_id   = Column(Integer, ForeignKey("xo_class.id", ondelete="RESTRICT"), nullable=True)
    sort_order  = Column(Integer, default=0)

    parent     = relationship("XOClass", remote_side=[id], back_populates="children")
    children   = relationship("XOClass", back_populates="parent")
    param_defs = relationship("XOParamDef", back_populates="xo_class", cascade="all, delete-orphan")
    role_defs  = relationship("XORoleDef",  back_populates="xo_class", cascade="all, delete-orphan")
    instances  = relationship("XOInstance", back_populates="xo_class")


class XOParamDef(Base):
    __tablename__ = "xo_param_def"

    id           = Column(Integer, primary_key=True, index=True)
    xo_class_id  = Column(Integer, ForeignKey("xo_class.id",        ondelete="CASCADE"), nullable=False)
    param_def_id = Column(Integer, ForeignKey("param_definition.id", ondelete="CASCADE"), nullable=False)
    is_inherited = Column(Boolean, default=True)
    sort_order   = Column(Integer, default=0)

    xo_class         = relationship("XOClass",        back_populates="param_defs")
    param_definition = relationship("ParamDefinition", back_populates="xo_param_defs")


class XORoleDef(Base):
    __tablename__ = "xo_role_def"

    id           = Column(Integer, primary_key=True, index=True)
    xo_class_id  = Column(Integer, ForeignKey("xo_class.id", ondelete="CASCADE"), nullable=False)
    name         = Column(String(100), nullable=False)
    description  = Column(Text, nullable=True)
    is_required  = Column(Boolean, default=True)
    subject_type = Column(String(50))

    xo_class    = relationship("XOClass",      back_populates="role_defs")
    assignments = relationship("XORoleAssign", back_populates="role_def", cascade="all, delete-orphan")


class XOInstance(Base):
    __tablename__ = "xo_instance"

    id           = Column(Integer, primary_key=True, index=True)
    xo_class_id  = Column(Integer, ForeignKey("xo_class.id", ondelete="RESTRICT"), nullable=False)
    number       = Column(String(50), nullable=True)
    op_date      = Column(Date, nullable=False)
    status       = Column(String(20), nullable=False, default="draft")
    notes        = Column(Text, nullable=True)
    created_at   = Column(DateTime, server_default=func.now())
    created_by   = Column(String(100), nullable=True)

    xo_class     = relationship("XOClass",       back_populates="instances")
    param_values = relationship("XOParamValue",  back_populates="xo_instance", cascade="all, delete-orphan")
    role_assigns = relationship("XORoleAssign",  back_populates="xo_instance", cascade="all, delete-orphan")
    lines        = relationship("XOLine",        back_populates="xo_instance", cascade="all, delete-orphan")


class XOParamValue(Base):
    __tablename__ = "xo_param_value"

    id            = Column(Integer, primary_key=True, index=True)
    xo_id         = Column(Integer, ForeignKey("xo_instance.id",     ondelete="CASCADE"), nullable=False)
    param_def_id  = Column(Integer, ForeignKey("param_definition.id", ondelete="CASCADE"), nullable=False)
    numeric_value = Column(Numeric(15, 4), nullable=True)
    text_value    = Column(Text,           nullable=True)
    enum_value_id = Column(Integer, ForeignKey("enum_value.id", ondelete="SET NULL"), nullable=True)

    xo_instance      = relationship("XOInstance",     back_populates="param_values")
    param_definition = relationship("ParamDefinition", back_populates="xo_param_values")
    enum_value       = relationship("EnumValue",       back_populates="xo_param_values")


class XORoleAssign(Base):
    __tablename__ = "xo_role_assign"

    id           = Column(Integer, primary_key=True, index=True)
    xo_id        = Column(Integer, ForeignKey("xo_instance.id",  ondelete="CASCADE"), nullable=False)
    role_def_id  = Column(Integer, ForeignKey("xo_role_def.id",  ondelete="CASCADE"), nullable=False)
    subject_id   = Column(Integer, nullable=True)
    subject_type = Column(String(50),  nullable=True)
    subject_name = Column(String(255), nullable=False)

    xo_instance = relationship("XOInstance", back_populates="role_assigns")
    role_def    = relationship("XORoleDef",  back_populates="assignments")


class XOLine(Base):
    __tablename__ = "xo_line"

    id         = Column(Integer, primary_key=True, index=True)
    xo_id      = Column(Integer, ForeignKey("xo_instance.id", ondelete="CASCADE"),   nullable=False)
    line_order = Column(Integer, nullable=False)
    product_id = Column(Integer, ForeignKey("product.id",     ondelete="RESTRICT"),  nullable=True)
    quantity   = Column(Numeric(15, 4), nullable=False)
    price      = Column(Numeric(10, 2), nullable=True)
    unit_name  = Column(String(50),     nullable=True)

    xo_instance = relationship("XOInstance", back_populates="lines")
    product     = relationship("Product",    back_populates="xo_lines")
