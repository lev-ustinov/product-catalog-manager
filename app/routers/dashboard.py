"""
Dashboard and analytics endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import List

from database import get_db
from auth import verify_token
from models import Category, Product, ParamDefinition, XOInstance
from schemas import (
    DashboardStats, AnalyticsResponse,
    CategoryDistribution, CategoryPriceAvg, ParamUsage, XOMonthly,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get(
    "/dashboard/stats",
    response_model=DashboardStats,
    summary="Статистика для дашборда",
    description="Возвращает общее количество категорий, товаров, параметров и экземпляров ХО.",
)
def dashboard_stats(
    _role: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    categories = db.query(func.count(Category.id)).scalar()
    products = db.query(func.count(Product.id)).scalar()
    params = db.query(func.count(ParamDefinition.id)).scalar()
    xo_instances = db.query(func.count(XOInstance.id)).scalar()
    return DashboardStats(
        categories=categories,
        products=products,
        params=params,
        xo_instances=xo_instances,
    )


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    summary="Агрегированная аналитика",
    description=(
        "Возвращает данные для графиков: распределение товаров по категориям, "
        "средняя цена по категориям, топ используемых параметров, "
        "количество ХО по месяцам."
    ),
)
def analytics(
    _role: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    # 1. Distribution of products per category (top-20)
    dist_rows = db.execute(text("""
        SELECT c.name AS category_name, COUNT(p.id) AS product_count
        FROM category c
        LEFT JOIN product p ON p."Category_id" = c.id
        GROUP BY c.id, c.name
        HAVING COUNT(p.id) > 0
        ORDER BY product_count DESC
        LIMIT 20
    """)).fetchall()
    category_distribution = [
        CategoryDistribution(category_name=r.category_name, product_count=r.product_count)
        for r in dist_rows
    ]

    # 2. Average price per category (top-20)
    avg_rows = db.execute(text("""
        SELECT c.name AS category_name, ROUND(AVG(p.price)::numeric, 2) AS avg_price
        FROM category c
        JOIN product p ON p."Category_id" = c.id
        GROUP BY c.id, c.name
        ORDER BY avg_price DESC
        LIMIT 20
    """)).fetchall()
    category_avg_price = [
        CategoryPriceAvg(category_name=r.category_name, avg_price=float(r.avg_price))
        for r in avg_rows
    ]

    # 3. Most-used parameters (by number of products having a value)
    param_rows = db.execute(text("""
        SELECT pd.name AS param_name,
               (SELECT COUNT(*) FROM product_param_numeric ppn WHERE ppn.param_id = pd.id)
               + (SELECT COUNT(*) FROM product_param_enum ppe WHERE ppe.param_id = pd.id)
               AS usage_count
        FROM param_definition pd
        ORDER BY usage_count DESC
        LIMIT 15
    """)).fetchall()
    param_usage = [
        ParamUsage(param_name=r.param_name, usage_count=r.usage_count)
        for r in param_rows
        if r.usage_count > 0
    ]

    # 4. XO instances per month (last 12 months)
    xo_rows = db.execute(text("""
        -- Last 24 months that actually have data (no fixed date cutoff that ages out)
        SELECT month, cnt FROM (
            SELECT TO_CHAR(DATE_TRUNC('month', op_date::timestamp), 'YYYY-MM') AS month,
                   COUNT(*) AS cnt
            FROM xo_instance
            GROUP BY DATE_TRUNC('month', op_date::timestamp)
            ORDER BY DATE_TRUNC('month', op_date::timestamp) DESC
            LIMIT 24
        ) t
        ORDER BY month
    """)).fetchall()
    xo_monthly = [
        XOMonthly(month=r.month, count=r.cnt)
        for r in xo_rows
    ]

    return AnalyticsResponse(
        category_distribution=category_distribution,
        category_avg_price=category_avg_price,
        param_usage=param_usage,
        xo_monthly=xo_monthly,
    )
