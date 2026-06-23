from sqlalchemy.orm import Session
from sqlalchemy import text
from models import Category, Product, EnumClass, EnumValue, ParamDefinition, CategoryParam, ProductParamNumeric, ProductParamEnum
from schemas import (
    CategoryCreate, CategoryUpdate, ProductCreate, ProductUpdate,
    DescendantInfo, ParentInfo, TerminalProduct, CycleCheckResult,
    ParamDefinitionCreate, ParamDefinitionUpdate,
    CategoryParamCreate, ProductParamNumericSet, ProductParamEnumSet,
)
from typing import List, Optional


# =============================================
# КАТЕГОРИИ
# =============================================

def get_category(db: Session, category_id: int):
    return db.query(Category).filter(Category.id == category_id).first()


def create_category(db: Session, category: CategoryCreate):
    result = db.execute(
        text("SELECT add_category(:name, :parent_id, :packaging_unit_name)"),
        {"name": category.name, "parent_id": category.Category_id,
         "packaging_unit_name": category.packaging_unit_name}
    )
    new_id = result.scalar()
    db.commit()
    return get_category(db, new_id)


def update_category(db: Session, category_id: int, updates: CategoryUpdate):
    db.execute(
        text("SELECT update_category(:id, :name, :parent_id, :packaging_unit_name, :sort_order)"),
        {"id": category_id, "name": updates.name, "parent_id": updates.Category_id,
         "packaging_unit_name": updates.packaging_unit_name, "sort_order": updates.sort_order}
    )
    db.commit()
    return get_category(db, category_id)


def delete_category(db: Session, category_id: int):
    db.execute(text("SELECT delete_category(:id)"), {"id": category_id})
    db.commit()


def move_category(db: Session, category_id: int, new_parent_id: Optional[int]):
    db.execute(text("SELECT move_category(:id, :new_parent)"),
               {"id": category_id, "new_parent": new_parent_id})
    db.commit()
    return get_category(db, category_id)


def reorder_categories(db: Session, parent_id: Optional[int], ordered_ids: List[int]):
    db.execute(text("SELECT reorder_categories(:parent_id, :ids::INTEGER[])"),
               {"parent_id": parent_id, "ids": ordered_ids})
    db.commit()


def get_descendants(db: Session, category_id: int) -> List[DescendantInfo]:
    result = db.execute(
        text("SELECT id, name, level, is_product, product_id, sort_order FROM get_all_descendants(:id)"),
        {"id": category_id}
    )
    return [DescendantInfo(id=r.id, name=r.name, level=r.level,
                           is_product=r.is_product, product_id=r.product_id, sort_order=r.sort_order)
            for r in result.fetchall()]


def get_parents(db: Session, category_id: int) -> List[ParentInfo]:
    result = db.execute(
        text("SELECT id, name, level FROM get_all_parents(:id)"), {"id": category_id}
    )
    return [ParentInfo(id=r.id, name=r.name, level=r.level) for r in result.fetchall()]


def get_terminal_products(db: Session, category_id: int) -> List[TerminalProduct]:
    result = db.execute(
        text("SELECT product_id, product_name, price, brand, description, packaging_unit_value "
             "FROM get_terminal_products(:id)"), {"id": category_id}
    )
    return [TerminalProduct(product_id=r.product_id, product_name=r.product_name, price=r.price,
                            brand=r.brand, description=r.description,
                            packaging_unit_value=r.packaging_unit_value)
            for r in result.fetchall()]


def check_cycles(db: Session) -> CycleCheckResult:
    result = db.execute(text("SELECT cycle_found, cycle_path FROM check_cycles()"))
    row = result.fetchone()
    return CycleCheckResult(cycle_found=row.cycle_found, cycle_path=row.cycle_path)


# =============================================
# ТОВАРЫ
# =============================================

def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()


def create_product(db: Session, product: ProductCreate):
    result = db.execute(
        text("SELECT add_product(:name, :category_id, :price, :brand, :description, :packaging_unit_value)"),
        {"name": product.name, "category_id": product.Category_id, "price": product.price,
         "brand": product.brand, "description": product.description,
         "packaging_unit_value": product.packaging_unit_value}
    )
    new_id = result.scalar()
    db.commit()
    return get_product(db, new_id)


def update_product(db: Session, product_id: int, updates: ProductUpdate):
    db.execute(
        text("SELECT update_product(:id, :name, :category_id, :price, :brand, :description, :packaging_unit_value, :sort_order)"),
        {"id": product_id, "name": updates.name, "category_id": updates.Category_id,
         "price": updates.price, "brand": updates.brand, "description": updates.description,
         "packaging_unit_value": updates.packaging_unit_value, "sort_order": updates.sort_order}
    )
    db.commit()
    return get_product(db, product_id)


def delete_product(db: Session, product_id: int):
    db.execute(text("SELECT delete_product(:id)"), {"id": product_id})
    db.commit()


def move_product(db: Session, product_id: int, new_category_id: int):
    db.execute(text("SELECT move_product(:id, :new_category)"),
               {"id": product_id, "new_category": new_category_id})
    db.commit()
    return get_product(db, product_id)


def reorder_products(db: Session, category_id: int, ordered_ids: List[int]):
    db.execute(text("SELECT reorder_products(:category_id, :ids::INTEGER[])"),
               {"category_id": category_id, "ids": ordered_ids})
    db.commit()


def get_full_tree(db: Session, root_category_id: Optional[int] = None) -> dict:
    if root_category_id:
        root = db.query(Category).filter(Category.id == root_category_id).first()
        if not root:
            return {}
        return _build_category_tree(root, db)
    roots = db.query(Category).filter(Category.Category_id.is_(None)).order_by(Category.sort_order).all()
    return {"name": "Все категории", "id": None,
            "children": [_build_category_tree(r, db) for r in roots]}


def _build_category_tree(category: Category, db: Session) -> dict:
    children_categories = db.query(Category).filter(
        Category.Category_id == category.id).order_by(Category.sort_order).all()
    products = db.query(Product).filter(
        Product.Category_id == category.id).order_by(Product.sort_order).all()
    node = {
        "id": category.id, "name": category.name, "type": "category",
        "packaging_unit_name": category.packaging_unit_name,
        "sort_order": category.sort_order, "children": []
    }
    for child in children_categories:
        node["children"].append(_build_category_tree(child, db))
    for product in products:
        node["children"].append({
            "id": product.id, "name": product.name, "type": "product",
            "price": float(product.price) if product.price else None,
            "brand": product.brand, "description": product.description,
            "packaging_unit_value": float(product.packaging_unit_value) if product.packaging_unit_value else None,
            "sort_order": product.sort_order, "children": []
        })
    return node


# =============================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================

def get_all_enum_classes(db: Session):
    result = db.execute(text("SELECT * FROM get_all_enum_classes()"))
    return result.fetchall()


def get_enum_class_by_id(db: Session, enum_class_id: int):
    return db.query(EnumClass).filter(EnumClass.id == enum_class_id).first()


def get_enum_class_by_name(db: Session, name: str):
    return db.query(EnumClass).filter(EnumClass.name == name).first()


def create_enum_class(db: Session, name: str, description: str = None):
    result = db.execute(text("SELECT create_enum_class(:name, :desc)"),
                        {"name": name, "desc": description})
    new_id = result.scalar()
    db.commit()
    return get_enum_class_by_id(db, new_id)


def update_enum_class(db: Session, enum_class_id: int, name: str = None, description: str = None):
    enum_class = get_enum_class_by_id(db, enum_class_id)
    if not enum_class:
        return None
    if name is not None:
        enum_class.name = name
    if description is not None:
        enum_class.description = description
    db.commit()
    db.refresh(enum_class)
    return enum_class


def delete_enum_class(db: Session, enum_class_id: int):
    db.execute(text("SELECT delete_enum_class(:id)"), {"id": enum_class_id})
    db.commit()


def get_enum_values(db: Session, enum_class_id: int):
    result = db.execute(text("SELECT * FROM get_enum_values(:class_id)"),
                        {"class_id": enum_class_id})
    return result.fetchall()


def get_enum_value_by_id(db: Session, value_id: int):
    result = db.execute(text("SELECT * FROM select_enum_value(:id)"), {"id": value_id})
    return result.fetchone()


def add_enum_value(db: Session, enum_class_id: int, value: str, sort_order: int = None):
    result = db.execute(text("SELECT add_enum_value(:class_id, :val, :order)"),
                        {"class_id": enum_class_id, "val": value, "order": sort_order})
    new_id = result.scalar()
    db.commit()
    result = db.execute(
        text("SELECT * FROM get_enum_values(:class_id) WHERE id = :id"),
        {"class_id": enum_class_id, "id": new_id}
    )
    return result.fetchone()


def update_enum_value(db: Session, value_id: int, new_value: str = None,
                      sort_order: int = None, is_active: bool = None):
    db.execute(text("SELECT update_enum_value(:id, :val, :order, :active)"),
               {"id": value_id, "val": new_value, "order": sort_order, "active": is_active})
    db.commit()
    result = db.execute(
        text("SELECT * FROM get_enum_values((SELECT enum_class_id FROM enum_value WHERE id = :id)) WHERE id = :id"),
        {"id": value_id}
    )
    return result.fetchone()


def delete_enum_value(db: Session, value_id: int):
    db.execute(text("SELECT delete_enum_value(:id)"), {"id": value_id})
    db.commit()


def reorder_enum_values(db: Session, enum_class_id: int, value_ids: List[int]):
    db.execute(text("SELECT reorder_enum_values(:class_id, :ids::INTEGER[])"),
               {"class_id": enum_class_id, "ids": value_ids})
    db.commit()


def enum_class_exists(db: Session, name: str, exclude_id: int = None):
    result = db.execute(text("SELECT enum_class_exists(:name, :exclude_id)"),
                        {"name": name, "exclude_id": exclude_id})
    return result.scalar()


# =============================================
# ОПРЕДЕЛЕНИЯ ПАРАМЕТРОВ
# =============================================

def get_all_param_definitions(db: Session):
    """Получить все определения параметров."""
    result = db.execute(text("SELECT * FROM get_all_param_definitions()"))
    return result.fetchall()


def get_param_definition(db: Session, param_id: int):
    return db.query(ParamDefinition).filter(ParamDefinition.id == param_id).first()


def create_param_definition(db: Session, param: ParamDefinitionCreate):
    result = db.execute(
        text("SELECT add_param_definition(:name, :desc, :ptype, :unit, :minv, :maxv, :enum_class, :req)"),
        {
            "name": param.name,
            "desc": param.description,
            "ptype": param.param_type,
            "unit": param.unit,
            "minv": param.min_value,
            "maxv": param.max_value,
            "enum_class": param.enum_class_id,
            "req": param.is_required,
        }
    )
    new_id = result.scalar()
    db.commit()
    return get_param_definition(db, new_id)


def update_param_definition(db: Session, param_id: int, updates: ParamDefinitionUpdate):
    db.execute(
        text("SELECT update_param_definition(:id, :name, :desc, :unit, :minv, :maxv, :req)"),
        {
            "id": param_id,
            "name": updates.name,
            "desc": updates.description,
            "unit": updates.unit,
            "minv": updates.min_value,
            "maxv": updates.max_value,
            "req": updates.is_required,
        }
    )
    db.commit()
    return get_param_definition(db, param_id)


def delete_param_definition(db: Session, param_id: int):
    db.execute(text("SELECT delete_param_definition(:id)"), {"id": param_id})
    db.commit()


# =============================================
# ПАРАМЕТРЫ КАТЕГОРИЙ (СХЕМА)
# =============================================

def assign_param_to_category(db: Session, category_id: int, cp: CategoryParamCreate):
    """Назначить параметр категории."""
    db.execute(
        text("SELECT assign_param_to_category(:cat, :param, :inh, :ord)"),
        {"cat": category_id, "param": cp.param_id,
         "inh": cp.is_inherited, "ord": cp.sort_order}
    )
    db.commit()


def remove_param_from_category(db: Session, category_id: int, param_id: int):
    """Снять параметр с категории."""
    db.execute(text("SELECT remove_param_from_category(:cat, :param)"),
               {"cat": category_id, "param": param_id})
    db.commit()


def get_category_params(db: Session, category_id: int):
    """Получить параметры категории (с унаследованными от предков)."""
    result = db.execute(
        text("SELECT * FROM get_category_params(:id)"), {"id": category_id}
    )
    return result.fetchall()


def get_direct_category_params(db: Session, category_id: int):
    """Получить только непосредственно назначенные параметры категории."""
    result = db.execute(
        text("SELECT * FROM get_direct_category_params(:id)"), {"id": category_id}
    )
    return result.fetchall()


def update_category_param(db: Session, category_id: int, param_id: int,
                          is_inherited: bool = None, sort_order: int = None):
    """Обновить настройки параметра для категории."""
    cp = db.query(CategoryParam).filter(
        CategoryParam.category_id == category_id,
        CategoryParam.param_id == param_id
    ).first()
    if not cp:
        return None
    if is_inherited is not None:
        cp.is_inherited = is_inherited
    if sort_order is not None:
        cp.sort_order = sort_order
    db.commit()
    db.refresh(cp)
    return cp


# =============================================
# ЗНАЧЕНИЯ ПАРАМЕТРОВ ИЗДЕЛИЙ
# =============================================

def get_product_params(db: Session, product_id: int):
    """Получить все параметры и их значения для изделия."""
    result = db.execute(
        text("SELECT * FROM get_product_params(:id)"), {"id": product_id}
    )
    return result.fetchall()


def set_product_param_numeric(db: Session, product_id: int, data: ProductParamNumericSet):
    """Установить числовое значение параметра изделия (с проверкой ограничений)."""
    db.execute(
        text("SELECT set_product_param_numeric(:pid, :param, :val)"),
        {"pid": product_id, "param": data.param_id, "val": data.value}
    )
    db.commit()


def set_product_param_enum(db: Session, product_id: int, data: ProductParamEnumSet):
    """Установить enum-значение параметра изделия."""
    db.execute(
        text("SELECT set_product_param_enum(:pid, :param, :evid)"),
        {"pid": product_id, "param": data.param_id, "evid": data.enum_value_id}
    )
    db.commit()


def delete_product_param(db: Session, product_id: int, param_id: int):
    """Удалить значение параметра изделия."""
    db.execute(text("SELECT delete_product_param(:pid, :param)"),
               {"pid": product_id, "param": param_id})
    db.commit()


# =============================================
# ПОИСК И АГРЕГАТЫ
# =============================================

def get_param_aggregates(db: Session, category_id: int, param_id: int):
    """Агрегаты числового параметра по категории (с потомками): min, max, avg, sum, count."""
    result = db.execute(
        text("SELECT * FROM get_param_aggregates(:cat, :param)"),
        {"cat": category_id, "param": param_id}
    )
    return result.fetchone()


def search_products_by_param(db: Session, category_id: int, param_id: int,
                              num_min=None, num_max=None, enum_value_id=None):
    """Поиск изделий в категории (с потомками) по значению параметра."""
    result = db.execute(
        text("SELECT * FROM search_products_by_params(:cat, :param, :nmin, :nmax, :evid)"),
        {"cat": category_id, "param": param_id,
         "nmin": num_min, "nmax": num_max, "evid": enum_value_id}
    )
    return result.fetchall()


def search_products_multi_filter(db: Session, category_id: int, filters: list) -> list:
    """
    Поиск изделий в категории (с потомками) по нескольким параметрам одновременно.
    filters: список словарей {"param_id": int, "num_min": ..., "num_max": ..., "enum_value_id": ...}
    Возвращает пересечение результатов всех фильтров.
    """
    if not filters:
        return []

    # Для каждого фильтра получаем множество product_id
    sets = []
    for f in filters:
        rows = search_products_by_param(
            db, category_id, f["param_id"],
            f.get("num_min"), f.get("num_max"), f.get("enum_value_id")
        )
        sets.append({r.product_id for r in rows})

    # Пересечение
    common_ids = set.intersection(*sets) if sets else set()

    if not common_ids:
        return []

    result = db.execute(
        text("""
            SELECT p.id AS product_id, p.name AS product_name,
                   p."Category_id" AS category_id, c.name AS category_name,
                   p.price, p.brand
            FROM product p
            JOIN category c ON c.id = p."Category_id"
            WHERE p.id = ANY(:ids)
            ORDER BY p.name
        """),
        {"ids": list(common_ids)}
    )
    return result.fetchall()


# =============================================
# ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ (ХО)
# =============================================

from models import XOClass, XOParamDef, XORoleDef, XOInstance, XOParamValue, XORoleAssign, XOLine
from schemas import (
    XOClassCreate, XOClassUpdate,
    XOParamDefCreate, XORoleDefCreate,
    XOInstanceCreate, XOInstanceUpdate,
    XOParamValueSet, XORoleAssignCreate, XOLineCreate,
)


# ===== КЛАССИФИКАТОР ХО =====

def get_xo_class(db: Session, xo_class_id: int):
    return db.query(XOClass).filter(XOClass.id == xo_class_id).first()


def get_all_xo_classes(db: Session):
    result = db.execute(text("SELECT * FROM get_xo_class_tree(NULL)"))
    return result.fetchall()


def create_xo_class(db: Session, data: XOClassCreate):
    result = db.execute(
        text("SELECT add_xo_class(:name, :desc, :parent, :sort)"),
        {"name": data.name, "desc": data.description,
         "parent": data.parent_id, "sort": data.sort_order}
    )
    new_id = result.scalar()
    db.commit()
    return get_xo_class(db, new_id)


def update_xo_class(db: Session, xo_class_id: int, data: XOClassUpdate):
    db.execute(
        text("SELECT update_xo_class(:id, :name, :desc, :sort)"),
        {"id": xo_class_id, "name": data.name,
         "desc": data.description, "sort": data.sort_order}
    )
    db.commit()
    return get_xo_class(db, xo_class_id)


def delete_xo_class(db: Session, xo_class_id: int):
    db.execute(text("SELECT delete_xo_class(:id)"), {"id": xo_class_id})
    db.commit()


def move_xo_class(db: Session, xo_class_id: int, new_parent_id: Optional[int]):
    db.execute(text("SELECT move_xo_class(:id, :parent)"),
               {"id": xo_class_id, "parent": new_parent_id})
    db.commit()
    return get_xo_class(db, xo_class_id)


# ===== ПАРАМЕТРЫ КЛАССОВ ХО =====

def get_xo_class_template(db: Session, xo_class_id: int):
    result = db.execute(
        text("SELECT * FROM get_xo_class_template(:id)"), {"id": xo_class_id}
    )
    return result.fetchall()


def assign_param_to_xo_class(db: Session, xo_class_id: int, data: XOParamDefCreate):
    db.execute(
        text("SELECT assign_param_to_xo_class(:cls, :param, :inh, :ord)"),
        {"cls": xo_class_id, "param": data.param_def_id,
         "inh": data.is_inherited, "ord": data.sort_order}
    )
    db.commit()


def remove_param_from_xo_class(db: Session, xo_class_id: int, param_def_id: int):
    db.execute(text("SELECT remove_param_from_xo_class(:cls, :param)"),
               {"cls": xo_class_id, "param": param_def_id})
    db.commit()


# ===== РОЛИ КЛАССОВ ХО =====

def get_xo_class_roles(db: Session, xo_class_id: int):
    result = db.execute(
        text("SELECT * FROM get_xo_class_roles(:id)"), {"id": xo_class_id}
    )
    return result.fetchall()


def create_xo_role_def(db: Session, xo_class_id: int, data: XORoleDefCreate):
    result = db.execute(
        text("SELECT add_xo_role_def(:cls, :name, :desc, :req, :stype)"),
        {"cls": xo_class_id, "name": data.name, "desc": data.description,
         "req": data.is_required, "stype": data.subject_type}
    )
    new_id = result.scalar()
    db.commit()
    return db.query(XORoleDef).filter(XORoleDef.id == new_id).first()


def delete_xo_role_def(db: Session, role_def_id: int):
    db.execute(text("SELECT delete_xo_role_def(:id)"), {"id": role_def_id})
    db.commit()


# ===== ЭКЗЕМПЛЯРЫ ХО =====

def get_xo_instance(db: Session, xo_id: int):
    return db.query(XOInstance).filter(XOInstance.id == xo_id).first()


def get_xo_instances(db: Session, xo_class_id: Optional[int] = None,
                     status: Optional[str] = None, limit: int = 100, offset: int = 0):
    q = db.query(XOInstance)
    if xo_class_id is not None:
        q = q.filter(XOInstance.xo_class_id == xo_class_id)
    if status is not None:
        q = q.filter(XOInstance.status == status)
    return q.order_by(XOInstance.op_date.desc(), XOInstance.id.desc()) \
             .limit(limit).offset(offset).all()


def create_xo_instance(db: Session, data: XOInstanceCreate):
    import datetime
    result = db.execute(
        text("SELECT create_xo_instance(:cls, :num, :dt, :notes, :by)"),
        {"cls": data.xo_class_id, "num": data.number,
         "dt": data.op_date or datetime.date.today(),
         "notes": data.notes, "by": data.created_by}
    )
    new_id = result.scalar()
    db.commit()
    return get_xo_instance(db, new_id)


def update_xo_instance(db: Session, xo_id: int, data: XOInstanceUpdate):
    db.execute(
        text("SELECT update_xo_instance(:id, :num, :dt, :notes)"),
        {"id": xo_id, "num": data.number, "dt": data.op_date, "notes": data.notes}
    )
    db.commit()
    return get_xo_instance(db, xo_id)


def post_xo_instance(db: Session, xo_id: int):
    db.execute(text("SELECT post_xo(:id)"), {"id": xo_id})
    db.commit()
    return get_xo_instance(db, xo_id)


def cancel_xo_instance(db: Session, xo_id: int, reason: Optional[str] = None):
    db.execute(text("SELECT cancel_xo(:id, :reason)"), {"id": xo_id, "reason": reason})
    db.commit()
    return get_xo_instance(db, xo_id)

def delete_xo_instance(db: Session, xo_id: int):
    """Удалить экземпляр ХО (только если статус draft)."""
    xo = db.query(XOInstance).filter(XOInstance.id == xo_id).first()
    if not xo:
        raise ValueError(f"Экземпляр ХО id={xo_id} не найден")
    if xo.status != 'draft':
        raise ValueError(f"Нельзя удалить ХО в статусе '{xo.status}'. Только draft.")
    db.delete(xo)
    db.commit()

# ===== ПАРАМЕТРЫ ЭКЗЕМПЛЯРОВ ХО =====

def get_xo_params(db: Session, xo_id: int):
    result = db.execute(text("SELECT * FROM get_xo_params(:id)"), {"id": xo_id})
    return result.fetchall()


def set_xo_param_value(db: Session, xo_id: int, data: XOParamValueSet):
    db.execute(
        text("SELECT set_xo_param_value(:xo, :param, :num, :txt, :ev)"),
        {"xo": xo_id, "param": data.param_def_id, "num": data.numeric_value,
         "txt": data.text_value, "ev": data.enum_value_id}
    )
    db.commit()


def delete_xo_param_value(db: Session, xo_id: int, param_def_id: int):
    db.execute(
        text("DELETE FROM xo_param_value WHERE xo_id=:xo AND param_def_id=:param"),
        {"xo": xo_id, "param": param_def_id}
    )
    db.commit()


# ===== РОЛИ ЭКЗЕМПЛЯРОВ ХО =====

def get_xo_roles(db: Session, xo_id: int):
    result = db.execute(text("SELECT * FROM get_xo_roles(:id)"), {"id": xo_id})
    return result.fetchall()


def assign_xo_role(db: Session, xo_id: int, data: XORoleAssignCreate):
    db.execute(
        text("SELECT assign_xo_role(:xo, :role, :name, :sid, :stype)"),
        {"xo": xo_id, "role": data.role_def_id, "name": data.subject_name,
         "sid": data.subject_id, "stype": data.subject_type}
    )
    db.commit()


def remove_xo_role(db: Session, xo_id: int, role_def_id: int):
    db.execute(
        text("DELETE FROM xo_role_assign WHERE xo_id=:xo AND role_def_id=:role"),
        {"xo": xo_id, "role": role_def_id}
    )
    db.commit()


# ===== СТРОКИ ХО =====

def get_xo_lines(db: Session, xo_id: int):
    result = db.execute(text("SELECT * FROM get_xo_lines(:id)"), {"id": xo_id})
    return result.fetchall()


def add_xo_line(db: Session, xo_id: int, data: XOLineCreate):
    result = db.execute(
        text("SELECT add_xo_line(:xo, :prod, :qty, :price, :unit)"),
        {"xo": xo_id, "prod": data.product_id, "qty": data.quantity,
         "price": data.price, "unit": data.unit_name}
    )
    new_id = result.scalar()
    db.commit()
    return new_id


def delete_xo_line(db: Session, line_id: int):
    db.execute(text("SELECT delete_xo_line(:id)"), {"id": line_id})
    db.commit()


# ===== ПОЛНОЕ ПРЕДСТАВЛЕНИЕ И ПОИСК =====

def get_xo_full(db: Session, xo_id: int):
    result = db.execute(text("SELECT * FROM get_xo_full(:id)"), {"id": xo_id})
    return result.fetchall()


def search_xo_by_param(db: Session, xo_class_id: int, param_def_id: int,
                        num_min=None, num_max=None, enum_val_id=None, status=None):
    result = db.execute(
        text("SELECT * FROM search_xo_by_param(:cls, :param, :nmin, :nmax, :ev, :st)"),
        {"cls": xo_class_id, "param": param_def_id,
         "nmin": num_min, "nmax": num_max, "ev": enum_val_id, "st": status}
    )
    return result.fetchall()
