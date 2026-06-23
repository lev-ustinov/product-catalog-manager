BEGIN;

-- =============================================
-- ТАБЛИЦА КАТЕГОРИЙ (иерархия)
-- =============================================
CREATE TABLE category (
    id                     SERIAL PRIMARY KEY,
    "Category_id"          INTEGER,
    name                   VARCHAR(255) NOT NULL,
    packaging_unit_name    VARCHAR(100),
    sort_order             INTEGER DEFAULT 0
);

ALTER TABLE category
ADD CONSTRAINT fk_category_parent
FOREIGN KEY ("Category_id")
REFERENCES category(id)
ON DELETE RESTRICT;

ALTER TABLE category
ADD CONSTRAINT uq_category_name_per_parent
UNIQUE (name, "Category_id");

-- =============================================
-- ТАБЛИЦА ТОВАРОВ (листья дерева)
-- =============================================
CREATE TABLE product (
    id                     SERIAL PRIMARY KEY,
    "Category_id"          INTEGER NOT NULL,
    name                   VARCHAR(255) NOT NULL,
    price                  NUMERIC(10,2) NOT NULL,
    brand                  VARCHAR(200),
    description            TEXT,
    packaging_unit_value   NUMERIC(10,2),
    sort_order             INTEGER DEFAULT 0
);

ALTER TABLE product
ADD CONSTRAINT fk_product_category
FOREIGN KEY ("Category_id")
REFERENCES category(id)
ON DELETE RESTRICT;

CREATE INDEX idx_category_parent ON category("Category_id");
CREATE INDEX idx_product_category ON product("Category_id");
CREATE INDEX idx_product_name ON product(name);

-- =============================================
-- ТАБЛИЦЫ ДЛЯ ПЕРЕЧИСЛЕНИЙ (ENUMS)
-- =============================================

CREATE TABLE IF NOT EXISTS enum_class (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enum_value (
    id            SERIAL PRIMARY KEY,
    enum_class_id INTEGER NOT NULL REFERENCES enum_class(id) ON DELETE CASCADE,
    value         VARCHAR(255) NOT NULL,
    sort_order    INTEGER DEFAULT 0,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_class_id, value)
);

CREATE INDEX IF NOT EXISTS idx_enum_value_class  ON enum_value(enum_class_id);
CREATE INDEX IF NOT EXISTS idx_enum_value_order  ON enum_value(sort_order);
CREATE INDEX IF NOT EXISTS idx_enum_value_active ON enum_value(is_active);

-- =============================================
-- РАСШИРЕНИЕ ТАБЛИЦЫ PRODUCT (ENUM-ПОЛЯ)
-- =============================================

ALTER TABLE product ADD COLUMN IF NOT EXISTS enum_product_type_id INTEGER REFERENCES enum_value(id) ON DELETE SET NULL;
ALTER TABLE product ADD COLUMN IF NOT EXISTS enum_unit_id         INTEGER REFERENCES enum_value(id) ON DELETE SET NULL;
ALTER TABLE product ADD COLUMN IF NOT EXISTS enum_season_id       INTEGER REFERENCES enum_value(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_product_enum_type   ON product(enum_product_type_id);
CREATE INDEX IF NOT EXISTS idx_product_enum_unit   ON product(enum_unit_id);
CREATE INDEX IF NOT EXISTS idx_product_enum_season ON product(enum_season_id);

-- =============================================
-- СИСТЕМА НАСТРАИВАЕМЫХ ПАРАМЕТРОВ
-- =============================================

-- Определение параметра (шаблон)
-- param_type: 'numeric' — числовой, 'enum' — перечисление
CREATE TABLE param_definition (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    description   TEXT,
    param_type    VARCHAR(20)  NOT NULL CHECK (param_type IN ('numeric', 'enum')),
    -- для числовых параметров:
    unit          VARCHAR(50),          -- единица измерения (мм, кг, °C …)
    min_value     NUMERIC(15,4),        -- нижняя граница допустимых значений
    max_value     NUMERIC(15,4),        -- верхняя граница допустимых значений
    -- для параметров-перечислений:
    enum_class_id INTEGER REFERENCES enum_class(id) ON DELETE SET NULL,
    -- общее:
    is_required   BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE param_definition IS
    'Справочник определений параметров (шаблоны). Параметр может быть числовым или перечислением.';
COMMENT ON COLUMN param_definition.param_type   IS 'numeric | enum';
COMMENT ON COLUMN param_definition.unit         IS 'Единица измерения числового параметра';
COMMENT ON COLUMN param_definition.min_value    IS 'Нижняя граница числового параметра (ограничение)';
COMMENT ON COLUMN param_definition.max_value    IS 'Верхняя граница числового параметра (ограничение)';
COMMENT ON COLUMN param_definition.enum_class_id IS 'Ссылка на класс перечисления (только для param_type=enum)';
COMMENT ON COLUMN param_definition.is_required   IS 'Обязателен ли параметр для заполнения';

CREATE INDEX idx_param_def_type  ON param_definition(param_type);
CREATE INDEX idx_param_def_enum  ON param_definition(enum_class_id);

-- Назначение параметра категории
-- Параметр может быть назначен нескольким категориям с разными настройками
CREATE TABLE category_param (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES category(id) ON DELETE CASCADE,
    param_id    INTEGER NOT NULL REFERENCES param_definition(id) ON DELETE CASCADE,
    is_inherited BOOLEAN DEFAULT TRUE, -- если TRUE — потомки категории наследуют этот параметр
    sort_order  INTEGER DEFAULT 0,
    UNIQUE(category_id, param_id)
);

COMMENT ON TABLE category_param IS
    'Связь параметра с категорией. is_inherited=TRUE означает, что параметр передаётся потомкам.';
COMMENT ON COLUMN category_param.is_inherited IS
    'TRUE — параметр наследуется подкатегориями; FALSE — только для прямой категории';

CREATE INDEX idx_catparam_cat   ON category_param(category_id);
CREATE INDEX idx_catparam_param ON category_param(param_id);

-- Значения числовых параметров изделий
CREATE TABLE product_param_numeric (
    id         SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    param_id   INTEGER NOT NULL REFERENCES param_definition(id) ON DELETE CASCADE,
    value      NUMERIC(15,4) NOT NULL,
    UNIQUE(product_id, param_id)
);

COMMENT ON TABLE product_param_numeric IS
    'Значения числовых параметров конкретных изделий.';

CREATE INDEX idx_ppn_product ON product_param_numeric(product_id);
CREATE INDEX idx_ppn_param   ON product_param_numeric(param_id);
CREATE INDEX idx_ppn_value   ON product_param_numeric(value);

-- Значения enum-параметров изделий
CREATE TABLE product_param_enum (
    id            SERIAL PRIMARY KEY,
    product_id    INTEGER NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    param_id      INTEGER NOT NULL REFERENCES param_definition(id) ON DELETE CASCADE,
    enum_value_id INTEGER NOT NULL REFERENCES enum_value(id) ON DELETE CASCADE,
    UNIQUE(product_id, param_id)
);

COMMENT ON TABLE product_param_enum IS
    'Значения параметров-перечислений конкретных изделий.';

CREATE INDEX idx_ppe_product ON product_param_enum(product_id);
CREATE INDEX idx_ppe_param   ON product_param_enum(param_id);


-- =============================================
-- ЗАПОЛНЕНИЕ CATEGORY
-- =============================================
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Товар', NULL, NULL);
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Семена', (SELECT id FROM category WHERE name='Товар' LIMIT 1), 'грамм');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Овощи', (SELECT id FROM category WHERE name='Семена' LIMIT 1), 'грамм');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Огурцы', (SELECT id FROM category WHERE name='Овощи' LIMIT 1), 'грамм');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Томаты', (SELECT id FROM category WHERE name='Овощи' LIMIT 1), 'грамм');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Цветы', (SELECT id FROM category WHERE name='Семена' LIMIT 1), 'грамм');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Розы', (SELECT id FROM category WHERE name='Цветы' LIMIT 1), 'грамм');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Тюльпаны', (SELECT id FROM category WHERE name='Цветы' LIMIT 1), 'грамм');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Саженцы', (SELECT id FROM category WHERE name='Товар' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Плодовые', (SELECT id FROM category WHERE name='Саженцы' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Смородина', (SELECT id FROM category WHERE name='Плодовые' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Малина', (SELECT id FROM category WHERE name='Плодовые' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Декоративные', (SELECT id FROM category WHERE name='Саженцы' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Розы кустовые', (SELECT id FROM category WHERE name='Декоративные' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Сакура', (SELECT id FROM category WHERE name='Декоративные' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Садовый инвентарь', (SELECT id FROM category WHERE name='Товар' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Инструменты', (SELECT id FROM category WHERE name='Садовый инвентарь' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Для рассады', (SELECT id FROM category WHERE name='Садовый инвентарь' LIMIT 1), 'шт.');
INSERT INTO category (name, "Category_id", packaging_unit_name) VALUES ('Для полива', (SELECT id FROM category WHERE name='Садовый инвентарь' LIMIT 1), 'шт.');

-- =============================================
-- ЗАПОЛНЕНИЕ PRODUCT
-- =============================================
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Огурец засолочный', (SELECT id FROM category WHERE name='Огурцы' LIMIT 1), 45.50, 'Семко', 'Раннеспелый сорт для засолки, устойчив к мучнистой росе', 5);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Томат сибирский', (SELECT id FROM category WHERE name='Томаты' LIMIT 1), 38.00, 'Аэлита', 'Холодостойкий сорт, плоды до 150 г', 10);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Томат японский', (SELECT id FROM category WHERE name='Томаты' LIMIT 1), 52.00, 'Гавриш', 'Крупноплодный, сладкий, для открытого грунта', 8);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Вилка садовая', (SELECT id FROM category WHERE name='Инструменты' LIMIT 1), 890.00, 'Fiskars', 'Стальная, эргономичная ручка, для перекопки', 1);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Секатор садовый', (SELECT id FROM category WHERE name='Инструменты' LIMIT 1), 1250.00, 'Gardena', 'С обрезиненной рукояткой, для обрезки веток', 1);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Ножницы садовые', (SELECT id FROM category WHERE name='Инструменты' LIMIT 1), 670.00, 'Bosch', 'Для стрижки кустов и газона', 1);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Горшок торфяной', (SELECT id FROM category WHERE name='Для рассады' LIMIT 1), 12.50, 'Jiffy', 'Биоразлагаемый, диаметр 8 см, 10 шт. в упаковке', 10);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Горшок пластиковый', (SELECT id FROM category WHERE name='Для рассады' LIMIT 1), 45.00, 'Россия', 'Квадратный 10×10 см, с поддоном', 1);
INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
VALUES ('Распылитель флакон', (SELECT id FROM category WHERE name='Для полива' LIMIT 1), 280.00, 'Gardena', 'Ручной триггерный распылитель 0,5 л', 1);

-- =============================================
-- МЕТАДАННЫЕ ПЕРЕЧИСЛЕНИЙ
-- =============================================
INSERT INTO enum_class (name, description) VALUES
    ('product_type',     'Тип товара (семена, саженцы, инвентарь, удобрения, средства защиты)'),
    ('unit',             'Единица измерения товара'),
    ('season',           'Сезонность товара'),
    ('planting_method',  'Способ посадки (открытый грунт, теплица, домашний)'),
    ('color',            'Цвет изделия'),
    ('material',         'Материал изделия')
ON CONFLICT (name) DO NOTHING;

INSERT INTO enum_value (enum_class_id, value, sort_order) VALUES
    ((SELECT id FROM enum_class WHERE name='product_type'), 'Семена', 1),
    ((SELECT id FROM enum_class WHERE name='product_type'), 'Саженцы', 2),
    ((SELECT id FROM enum_class WHERE name='product_type'), 'Инструменты', 3),
    ((SELECT id FROM enum_class WHERE name='product_type'), 'Удобрения', 4),
    ((SELECT id FROM enum_class WHERE name='product_type'), 'Средства защиты', 5)
ON CONFLICT (enum_class_id, value) DO NOTHING;

INSERT INTO enum_value (enum_class_id, value, sort_order) VALUES
    ((SELECT id FROM enum_class WHERE name='unit'), 'шт', 1),
    ((SELECT id FROM enum_class WHERE name='unit'), 'гр', 2),
    ((SELECT id FROM enum_class WHERE name='unit'), 'кг', 3),
    ((SELECT id FROM enum_class WHERE name='unit'), 'мл', 4),
    ((SELECT id FROM enum_class WHERE name='unit'), 'л',  5),
    ((SELECT id FROM enum_class WHERE name='unit'), 'уп', 6)
ON CONFLICT (enum_class_id, value) DO NOTHING;

INSERT INTO enum_value (enum_class_id, value, sort_order) VALUES
    ((SELECT id FROM enum_class WHERE name='season'), 'Весна', 1),
    ((SELECT id FROM enum_class WHERE name='season'), 'Лето', 2),
    ((SELECT id FROM enum_class WHERE name='season'), 'Осень', 3),
    ((SELECT id FROM enum_class WHERE name='season'), 'Зима', 4),
    ((SELECT id FROM enum_class WHERE name='season'), 'Круглогодично', 5)
ON CONFLICT (enum_class_id, value) DO NOTHING;

INSERT INTO enum_value (enum_class_id, value, sort_order) VALUES
    ((SELECT id FROM enum_class WHERE name='planting_method'), 'Открытый грунт', 1),
    ((SELECT id FROM enum_class WHERE name='planting_method'), 'Теплица', 2),
    ((SELECT id FROM enum_class WHERE name='planting_method'), 'Домашний', 3)
ON CONFLICT (enum_class_id, value) DO NOTHING;

INSERT INTO enum_value (enum_class_id, value, sort_order) VALUES
    ((SELECT id FROM enum_class WHERE name='color'), 'Красный', 1),
    ((SELECT id FROM enum_class WHERE name='color'), 'Жёлтый', 2),
    ((SELECT id FROM enum_class WHERE name='color'), 'Зелёный', 3),
    ((SELECT id FROM enum_class WHERE name='color'), 'Оранжевый', 4),
    ((SELECT id FROM enum_class WHERE name='color'), 'Розовый', 5),
    ((SELECT id FROM enum_class WHERE name='color'), 'Белый', 6),
    ((SELECT id FROM enum_class WHERE name='color'), 'Смесь', 7)
ON CONFLICT (enum_class_id, value) DO NOTHING;

INSERT INTO enum_value (enum_class_id, value, sort_order) VALUES
    ((SELECT id FROM enum_class WHERE name='material'), 'Сталь', 1),
    ((SELECT id FROM enum_class WHERE name='material'), 'Нержавеющая сталь', 2),
    ((SELECT id FROM enum_class WHERE name='material'), 'Пластик', 3),
    ((SELECT id FROM enum_class WHERE name='material'), 'Торф', 4),
    ((SELECT id FROM enum_class WHERE name='material'), 'Алюминий', 5),
    ((SELECT id FROM enum_class WHERE name='material'), 'Резина', 6)
ON CONFLICT (enum_class_id, value) DO NOTHING;

-- =============================================
-- МЕТАДАННЫЕ ПАРАМЕТРОВ (param_definition)
-- =============================================

-- Общие параметры для всех семян
INSERT INTO param_definition (name, description, param_type, unit, min_value, max_value, is_required)
VALUES
    ('Масса нетто',      'Масса содержимого упаковки', 'numeric', 'г',  0.1, 1000, TRUE),
    ('Всхожесть',        'Процент всхожести семян',    'numeric', '%',  0,   100,  FALSE),
    ('Срок хранения',    'Срок хранения в годах',      'numeric', 'лет',1,   10,   FALSE),
    ('Глубина посева',   'Рекомендуемая глубина посева','numeric','см', 0,   30,   FALSE),
    ('Период вегетации', 'Число дней от посева до сбора','numeric','дн',30, 365,  FALSE);

-- Параметры для саженцев
INSERT INTO param_definition (name, description, param_type, unit, min_value, max_value, is_required)
VALUES
    ('Высота саженца',   'Высота посадочного материала', 'numeric', 'см', 5, 200, FALSE),
    ('Возраст',          'Возраст саженца в годах',      'numeric', 'лет',1, 10,  FALSE),
    ('Диаметр кроны',    'Диаметр кроны в сантиметрах',  'numeric', 'см', 5, 500, FALSE);

-- Параметры для инструментов
INSERT INTO param_definition (name, description, param_type, unit, min_value, max_value, is_required)
VALUES
    ('Длина',            'Общая длина инструмента',      'numeric', 'мм', 50,  2500, FALSE),
    ('Масса',            'Вес изделия',                  'numeric', 'г',  50,  5000, FALSE),
    ('Ширина рабочей части', 'Ширина рабочего элемента', 'numeric', 'мм', 10,  500,  FALSE);

-- Параметры для горшков/рассадников
INSERT INTO param_definition (name, description, param_type, unit, min_value, max_value, is_required)
VALUES
    ('Диаметр',          'Диаметр горшка',               'numeric', 'см', 5,   60, FALSE),
    ('Объём',            'Объём горшка',                  'numeric', 'л',  0.1, 50, FALSE);

-- Параметры-перечисления (общие)
INSERT INTO param_definition (name, description, param_type, enum_class_id, is_required)
VALUES
    ('Сезон применения', 'Рекомендуемый сезон',
     'enum', (SELECT id FROM enum_class WHERE name='season'), FALSE),
    ('Способ выращивания','Способ посадки/выращивания',
     'enum', (SELECT id FROM enum_class WHERE name='planting_method'), FALSE),
    ('Цвет плода/цветка', 'Цвет основного элемента',
     'enum', (SELECT id FROM enum_class WHERE name='color'), FALSE),
    ('Материал',         'Основной материал изделия',
     'enum', (SELECT id FROM enum_class WHERE name='material'), FALSE);

-- =============================================
-- НАЗНАЧЕНИЕ ПАРАМЕТРОВ КАТЕГОРИЯМ
-- =============================================

-- Семена: масса, всхожесть, срок хранения, глубина посева, сезон, способ выращивания
INSERT INTO category_param (category_id, param_id, is_inherited, sort_order)
SELECT
    (SELECT id FROM category WHERE name='Семена'),
    pd.id, TRUE, pd.id
FROM param_definition pd
WHERE pd.name IN ('Масса нетто','Всхожесть','Срок хранения','Глубина посева','Период вегетации',
                  'Сезон применения','Способ выращивания','Цвет плода/цветка')
ON CONFLICT (category_id, param_id) DO NOTHING;

-- Саженцы: высота, возраст, диаметр кроны, сезон
INSERT INTO category_param (category_id, param_id, is_inherited, sort_order)
SELECT
    (SELECT id FROM category WHERE name='Саженцы'),
    pd.id, TRUE, pd.id
FROM param_definition pd
WHERE pd.name IN ('Высота саженца','Возраст','Диаметр кроны','Сезон применения','Цвет плода/цветка')
ON CONFLICT (category_id, param_id) DO NOTHING;

-- Инструменты: длина, масса, ширина, материал
INSERT INTO category_param (category_id, param_id, is_inherited, sort_order)
SELECT
    (SELECT id FROM category WHERE name='Инструменты'),
    pd.id, TRUE, pd.id
FROM param_definition pd
WHERE pd.name IN ('Длина','Масса','Ширина рабочей части','Материал')
ON CONFLICT (category_id, param_id) DO NOTHING;

-- Для рассады: диаметр, объём, материал
INSERT INTO category_param (category_id, param_id, is_inherited, sort_order)
SELECT
    (SELECT id FROM category WHERE name='Для рассады'),
    pd.id, TRUE, pd.id
FROM param_definition pd
WHERE pd.name IN ('Диаметр','Объём','Материал')
ON CONFLICT (category_id, param_id) DO NOTHING;

-- =============================================
-- ТЕСТОВЫЕ ЗНАЧЕНИЯ ПАРАМЕТРОВ ИЗДЕЛИЙ
-- =============================================

-- Огурец засолочный
INSERT INTO product_param_numeric (product_id, param_id, value)
SELECT
    (SELECT id FROM product WHERE name='Огурец засолочный'),
    (SELECT id FROM param_definition WHERE name='Масса нетто'), 5
ON CONFLICT (product_id, param_id) DO NOTHING;

INSERT INTO product_param_numeric (product_id, param_id, value)
SELECT
    (SELECT id FROM product WHERE name='Огурец засолочный'),
    (SELECT id FROM param_definition WHERE name='Всхожесть'), 92
ON CONFLICT (product_id, param_id) DO NOTHING;

INSERT INTO product_param_numeric (product_id, param_id, value)
SELECT
    (SELECT id FROM product WHERE name='Огурец засолочный'),
    (SELECT id FROM param_definition WHERE name='Период вегетации'), 45
ON CONFLICT (product_id, param_id) DO NOTHING;

INSERT INTO product_param_enum (product_id, param_id, enum_value_id)
SELECT
    (SELECT id FROM product WHERE name='Огурец засолочный'),
    (SELECT id FROM param_definition WHERE name='Сезон применения'),
    (SELECT ev.id FROM enum_value ev JOIN enum_class ec ON ec.id = ev.enum_class_id
     WHERE ec.name='season' AND ev.value='Весна')
ON CONFLICT (product_id, param_id) DO NOTHING;

INSERT INTO product_param_enum (product_id, param_id, enum_value_id)
SELECT
    (SELECT id FROM product WHERE name='Огурец засолочный'),
    (SELECT id FROM param_definition WHERE name='Способ выращивания'),
    (SELECT ev.id FROM enum_value ev JOIN enum_class ec ON ec.id = ev.enum_class_id
     WHERE ec.name='planting_method' AND ev.value='Открытый грунт')
ON CONFLICT (product_id, param_id) DO NOTHING;

-- Вилка садовая
INSERT INTO product_param_numeric (product_id, param_id, value)
SELECT
    (SELECT id FROM product WHERE name='Вилка садовая'),
    (SELECT id FROM param_definition WHERE name='Длина'), 870
ON CONFLICT (product_id, param_id) DO NOTHING;

INSERT INTO product_param_numeric (product_id, param_id, value)
SELECT
    (SELECT id FROM product WHERE name='Вилка садовая'),
    (SELECT id FROM param_definition WHERE name='Масса'), 680
ON CONFLICT (product_id, param_id) DO NOTHING;

INSERT INTO product_param_enum (product_id, param_id, enum_value_id)
SELECT
    (SELECT id FROM product WHERE name='Вилка садовая'),
    (SELECT id FROM param_definition WHERE name='Материал'),
    (SELECT ev.id FROM enum_value ev JOIN enum_class ec ON ec.id = ev.enum_class_id
     WHERE ec.name='material' AND ev.value='Сталь')
ON CONFLICT (product_id, param_id) DO NOTHING;

-- Горшок торфяной
INSERT INTO product_param_numeric (product_id, param_id, value)
SELECT
    (SELECT id FROM product WHERE name='Горшок торфяной'),
    (SELECT id FROM param_definition WHERE name='Диаметр'), 8
ON CONFLICT (product_id, param_id) DO NOTHING;

INSERT INTO product_param_enum (product_id, param_id, enum_value_id)
SELECT
    (SELECT id FROM product WHERE name='Горшок торфяной'),
    (SELECT id FROM param_definition WHERE name='Материал'),
    (SELECT ev.id FROM enum_value ev JOIN enum_class ec ON ec.id = ev.enum_class_id
     WHERE ec.name='material' AND ev.value='Торф')
ON CONFLICT (product_id, param_id) DO NOTHING;


-- =============================================
-- ФУНКЦИИ: БАЗОВЫЙ CRUD КАТЕГОРИЙ
-- =============================================

CREATE OR REPLACE FUNCTION add_category(
    p_name                VARCHAR(255),
    p_parent_id           INTEGER DEFAULT NULL,
    p_packaging_unit_name VARCHAR(100) DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE new_id INTEGER;
BEGIN
    INSERT INTO category (name, "Category_id", packaging_unit_name)
    VALUES (p_name, p_parent_id, p_packaging_unit_name)
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION add_product(
    p_name                 VARCHAR(255),
    p_category_id          INTEGER,
    p_price                NUMERIC(10,2),
    p_brand                VARCHAR(200) DEFAULT NULL,
    p_description          TEXT DEFAULT NULL,
    p_packaging_unit_value NUMERIC(10,2) DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE new_id INTEGER;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM category WHERE id = p_category_id) THEN
        RAISE EXCEPTION 'Категория с id=% не существует!', p_category_id;
    END IF;
    INSERT INTO product (name, "Category_id", price, brand, description, packaging_unit_value)
    VALUES (p_name, p_category_id, p_price, p_brand, p_description, p_packaging_unit_value)
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION move_category(
    p_category_id   INTEGER,
    p_new_parent_id INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM category WHERE id = p_category_id) THEN
        RAISE EXCEPTION 'Категория id=% не найдена!', p_category_id;
    END IF;
    IF p_category_id = p_new_parent_id THEN
        RAISE EXCEPTION 'Нельзя переместить категорию в саму себя!';
    END IF;
    IF p_new_parent_id IS NOT NULL THEN
        IF EXISTS (
            WITH RECURSIVE descendants AS (
                SELECT id FROM category WHERE id = p_category_id
                UNION ALL
                SELECT c.id FROM category c
                INNER JOIN descendants d ON c."Category_id" = d.id
            )
            SELECT 1 FROM descendants WHERE id = p_new_parent_id
        ) THEN
            RAISE EXCEPTION 'Нельзя переместить категорию в своего потомка (цикл)!';
        END IF;
    END IF;
    UPDATE category SET "Category_id" = p_new_parent_id WHERE id = p_category_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION move_product(
    p_product_id      INTEGER,
    p_new_category_id INTEGER
) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM product WHERE id = p_product_id) THEN
        RAISE EXCEPTION 'Товар id=% не найден!', p_product_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM category WHERE id = p_new_category_id) THEN
        RAISE EXCEPTION 'Категория id=% не существует!', p_new_category_id;
    END IF;
    UPDATE product SET "Category_id" = p_new_category_id WHERE id = p_product_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION delete_category(p_category_id INTEGER) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM category WHERE id = p_category_id) THEN
        RAISE EXCEPTION 'Категория id=% не найдена!', p_category_id;
    END IF;
    IF EXISTS (SELECT 1 FROM category WHERE "Category_id" = p_category_id) THEN
        RAISE EXCEPTION 'Нельзя удалить категорию — в ней есть подкатегории!';
    END IF;
    IF EXISTS (SELECT 1 FROM product WHERE "Category_id" = p_category_id) THEN
        RAISE EXCEPTION 'Нельзя удалить категорию — в ней есть товары!';
    END IF;
    DELETE FROM category WHERE id = p_category_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION delete_product(p_product_id INTEGER) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM product WHERE id = p_product_id) THEN
        RAISE EXCEPTION 'Товар id=% не найден!', p_product_id;
    END IF;
    DELETE FROM product WHERE id = p_product_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION check_cycles()
RETURNS TABLE (cycle_found BOOLEAN, cycle_path TEXT) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE search AS (
        SELECT id, "Category_id", ARRAY[id] AS path, FALSE AS has_cycle
        FROM category WHERE "Category_id" IS NOT NULL
        UNION ALL
        SELECT c.id, c."Category_id", path || c.id, c.id = ANY(path)
        FROM category c JOIN search s ON c."Category_id" = s.id
        WHERE NOT has_cycle
    )
    SELECT TRUE, array_to_string(path, ' → ')
    FROM search WHERE has_cycle LIMIT 1;
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Циклов нет'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_all_descendants(p_category_id INTEGER)
RETURNS TABLE (id INTEGER, name VARCHAR(255), level INTEGER, is_product BOOLEAN,
               product_id INTEGER, sort_order INTEGER, indented_name TEXT) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE cat_tree AS (
        SELECT c.id, c.name, 0 AS level, FALSE AS is_product, NULL::INTEGER AS product_id,
               c.sort_order, c.name::TEXT AS indented_name
        FROM category c WHERE c.id = p_category_id
        UNION ALL
        SELECT c.id, c.name, ct.level+1, FALSE, NULL, c.sort_order,
               REPEAT('    ', ct.level+1) || '├── ' || c.name
        FROM category c JOIN cat_tree ct ON c."Category_id" = ct.id
    ),
    prod_tree AS (
        SELECT p.id, p.name, ct.level+1, TRUE, p.id, p.sort_order,
               REPEAT('    ', ct.level+1) || '├── ' || p.name || ' (' || COALESCE(p.brand,'') || ')'
        FROM product p JOIN cat_tree ct ON p."Category_id" = ct.id
    )
    SELECT * FROM cat_tree UNION ALL SELECT * FROM prod_tree ORDER BY level, sort_order, name;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_all_parents(p_category_id INTEGER)
RETURNS TABLE (id INTEGER, name VARCHAR(255), level INTEGER) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE parents AS (
        SELECT c.id, c.name, c."Category_id", 0 AS level
        FROM category c WHERE c.id = p_category_id
        UNION ALL
        SELECT c.id, c.name, c."Category_id", p.level+1
        FROM category c JOIN parents p ON c.id = p."Category_id"
    )
    SELECT p.id, p.name, p.level FROM parents p ORDER BY p.level DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_terminal_products(p_category_id INTEGER)
RETURNS TABLE (product_id INTEGER, product_name VARCHAR(255), price NUMERIC(10,2),
               brand VARCHAR(200), description TEXT, packaging_unit_value NUMERIC(10,2)) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE subtree AS (
        SELECT id FROM category WHERE id = p_category_id
        UNION ALL
        SELECT c.id FROM category c JOIN subtree s ON c."Category_id" = s.id
    )
    SELECT p.id, p.name, p.price, p.brand, p.description, p.packaging_unit_value
    FROM product p JOIN subtree s ON p."Category_id" = s.id ORDER BY p.name;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION reorder_products(p_category_id INTEGER, p_product_ids INTEGER[]) RETURNS VOID AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM unnest(p_product_ids) AS pid
        LEFT JOIN product p ON p.id = pid
        WHERE p."Category_id" <> p_category_id OR p.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Один или несколько товаров не принадлежат указанной категории!';
    END IF;
    FOR i IN 1..array_length(p_product_ids,1) LOOP
        UPDATE product SET sort_order = i WHERE id = p_product_ids[i];
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION reorder_categories(p_parent_id INTEGER, p_category_ids INTEGER[]) RETURNS VOID AS $$
BEGIN
    IF p_parent_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM category WHERE id = p_parent_id) THEN
        RAISE EXCEPTION 'Родительская категория id=% не существует!', p_parent_id;
    END IF;
    IF EXISTS (
        SELECT 1 FROM unnest(p_category_ids) AS cid
        LEFT JOIN category c ON c.id = cid
        WHERE c."Category_id" IS DISTINCT FROM p_parent_id OR c.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Одна или несколько категорий не являются прямыми потомками родителя id=%', p_parent_id;
    END IF;
    FOR i IN 1..array_length(p_category_ids,1) LOOP
        UPDATE category SET sort_order = i WHERE id = p_category_ids[i];
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_category(
    p_id                  INTEGER,
    p_name                VARCHAR(255) DEFAULT NULL,
    p_parent_id           INTEGER DEFAULT NULL,
    p_packaging_unit_name VARCHAR(100) DEFAULT NULL,
    p_sort_order          INTEGER DEFAULT NULL
) RETURNS VOID AS $$
DECLARE current_parent INTEGER;
BEGIN
    SELECT "Category_id" INTO current_parent FROM category WHERE id = p_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Категория с id=% не найдена!', p_id; END IF;
    IF p_parent_id IS NOT NULL AND p_parent_id IS DISTINCT FROM current_parent THEN
        PERFORM move_category(p_id, p_parent_id);
    END IF;
    IF p_name IS NOT NULL THEN UPDATE category SET name = p_name WHERE id = p_id; END IF;
    IF p_packaging_unit_name IS NOT NULL THEN UPDATE category SET packaging_unit_name = p_packaging_unit_name WHERE id = p_id; END IF;
    IF p_sort_order IS NOT NULL THEN UPDATE category SET sort_order = p_sort_order WHERE id = p_id; END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_product(
    p_id                   INTEGER,
    p_name                 VARCHAR(255) DEFAULT NULL,
    p_category_id          INTEGER DEFAULT NULL,
    p_price                NUMERIC(10,2) DEFAULT NULL,
    p_brand                VARCHAR(200) DEFAULT NULL,
    p_description          TEXT DEFAULT NULL,
    p_packaging_unit_value NUMERIC(10,2) DEFAULT NULL,
    p_sort_order           INTEGER DEFAULT NULL
) RETURNS VOID AS $$
DECLARE current_category INTEGER;
BEGIN
    SELECT "Category_id" INTO current_category FROM product WHERE id = p_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Товар с id=% не найден!', p_id; END IF;
    IF p_category_id IS NOT NULL AND p_category_id IS DISTINCT FROM current_category THEN
        PERFORM move_product(p_id, p_category_id);
    END IF;
    IF p_name        IS NOT NULL THEN UPDATE product SET name = p_name WHERE id = p_id; END IF;
    IF p_price       IS NOT NULL THEN UPDATE product SET price = p_price WHERE id = p_id; END IF;
    IF p_brand       IS NOT NULL THEN UPDATE product SET brand = p_brand WHERE id = p_id; END IF;
    IF p_description IS NOT NULL THEN UPDATE product SET description = p_description WHERE id = p_id; END IF;
    IF p_packaging_unit_value IS NOT NULL THEN UPDATE product SET packaging_unit_value = p_packaging_unit_value WHERE id = p_id; END IF;
    IF p_sort_order  IS NOT NULL THEN UPDATE product SET sort_order = p_sort_order WHERE id = p_id; END IF;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- ФУНКЦИИ ПЕРЕЧИСЛЕНИЙ
-- =============================================

CREATE OR REPLACE FUNCTION get_all_enum_classes()
RETURNS TABLE(id INTEGER, name VARCHAR, description TEXT, values_count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT ec.id, ec.name, ec.description, COUNT(ev.id)::BIGINT
    FROM enum_class ec
    LEFT JOIN enum_value ev ON ev.enum_class_id = ec.id AND ev.is_active = TRUE
    GROUP BY ec.id ORDER BY ec.name;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_enum_values(p_class_id INTEGER)
RETURNS TABLE(id INTEGER, value VARCHAR, sort_order INTEGER, is_active BOOLEAN) AS $$
BEGIN
    RETURN QUERY
    SELECT ev.id, ev.value, ev.sort_order, ev.is_active
    FROM enum_value ev WHERE ev.enum_class_id = p_class_id ORDER BY ev.sort_order, ev.value;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION create_enum_class(p_name VARCHAR, p_description TEXT DEFAULT NULL)
RETURNS INTEGER AS $$
DECLARE new_id INTEGER;
BEGIN
    INSERT INTO enum_class (name, description) VALUES (p_name, p_description) RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION add_enum_value(p_class_id INTEGER, p_value VARCHAR, p_sort_order INTEGER DEFAULT NULL)
RETURNS INTEGER AS $$
DECLARE max_order INTEGER; new_order INTEGER; new_id INTEGER;
BEGIN
    IF p_sort_order IS NULL THEN
        SELECT COALESCE(MAX(sort_order),0)+1 INTO max_order FROM enum_value WHERE enum_class_id = p_class_id;
        new_order := max_order;
    ELSE new_order := p_sort_order; END IF;
    INSERT INTO enum_value (enum_class_id, value, sort_order, is_active)
    VALUES (p_class_id, p_value, new_order, TRUE) RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_enum_value(
    p_value_id INTEGER, p_new_value VARCHAR DEFAULT NULL,
    p_sort_order INTEGER DEFAULT NULL, p_is_active BOOLEAN DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF p_new_value  IS NOT NULL THEN UPDATE enum_value SET value = p_new_value,  updated_at=CURRENT_TIMESTAMP WHERE id=p_value_id; END IF;
    IF p_sort_order IS NOT NULL THEN UPDATE enum_value SET sort_order=p_sort_order,updated_at=CURRENT_TIMESTAMP WHERE id=p_value_id; END IF;
    IF p_is_active  IS NOT NULL THEN UPDATE enum_value SET is_active=p_is_active, updated_at=CURRENT_TIMESTAMP WHERE id=p_value_id; END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION delete_enum_value(p_value_id INTEGER) RETURNS VOID AS $$
BEGIN
    UPDATE enum_value SET is_active=FALSE, updated_at=CURRENT_TIMESTAMP WHERE id=p_value_id;
    UPDATE product SET enum_product_type_id=NULL WHERE enum_product_type_id=p_value_id;
    UPDATE product SET enum_unit_id=NULL WHERE enum_unit_id=p_value_id;
    UPDATE product SET enum_season_id=NULL WHERE enum_season_id=p_value_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION delete_enum_class(p_class_id INTEGER) RETURNS VOID AS $$
BEGIN DELETE FROM enum_class WHERE id=p_class_id; END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION reorder_enum_values(p_class_id INTEGER, p_value_ids INTEGER[]) RETURNS VOID AS $$
BEGIN
    FOR i IN 1..array_length(p_value_ids,1) LOOP
        UPDATE enum_value SET sort_order=i, updated_at=CURRENT_TIMESTAMP
        WHERE id=p_value_ids[i] AND enum_class_id=p_class_id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION select_enum_value(p_value_id INTEGER)
RETURNS TABLE(id INTEGER, value VARCHAR, class_name VARCHAR, class_description TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT ev.id, ev.value, ec.name, ec.description
    FROM enum_value ev JOIN enum_class ec ON ec.id=ev.enum_class_id WHERE ev.id=p_value_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION enum_class_exists(p_name VARCHAR, p_exclude_id INTEGER DEFAULT NULL)
RETURNS BOOLEAN AS $$
DECLARE exists_flag BOOLEAN;
BEGIN
    IF p_exclude_id IS NULL THEN
        SELECT EXISTS(SELECT 1 FROM enum_class WHERE name=p_name) INTO exists_flag;
    ELSE
        SELECT EXISTS(SELECT 1 FROM enum_class WHERE name=p_name AND id!=p_exclude_id) INTO exists_flag;
    END IF;
    RETURN exists_flag;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- ФУНКЦИИ ПАРАМЕТРЫ
-- =============================================

-- 1. Создать определение параметра
CREATE OR REPLACE FUNCTION add_param_definition(
    p_name          VARCHAR(255),
    p_description   TEXT,
    p_param_type    VARCHAR(20),     -- 'numeric' или 'enum'
    p_unit          VARCHAR(50)  DEFAULT NULL,
    p_min_value     NUMERIC(15,4) DEFAULT NULL,
    p_max_value     NUMERIC(15,4) DEFAULT NULL,
    p_enum_class_id INTEGER      DEFAULT NULL,
    p_is_required   BOOLEAN      DEFAULT FALSE
) RETURNS INTEGER AS $$
DECLARE new_id INTEGER;
BEGIN
    IF p_param_type NOT IN ('numeric','enum') THEN
        RAISE EXCEPTION 'param_type должен быть numeric или enum, получено: %', p_param_type;
    END IF;
    IF p_param_type = 'enum' AND p_enum_class_id IS NULL THEN
        RAISE EXCEPTION 'Для enum-параметра необходимо указать enum_class_id';
    END IF;
    INSERT INTO param_definition (name, description, param_type, unit, min_value, max_value, enum_class_id, is_required)
    VALUES (p_name, p_description, p_param_type, p_unit, p_min_value, p_max_value, p_enum_class_id, p_is_required)
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- 2. Обновить определение параметра
CREATE OR REPLACE FUNCTION update_param_definition(
    p_id            INTEGER,
    p_name          VARCHAR(255)  DEFAULT NULL,
    p_description   TEXT          DEFAULT NULL,
    p_unit          VARCHAR(50)   DEFAULT NULL,
    p_min_value     NUMERIC(15,4) DEFAULT NULL,
    p_max_value     NUMERIC(15,4) DEFAULT NULL,
    p_is_required   BOOLEAN       DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM param_definition WHERE id=p_id) THEN
        RAISE EXCEPTION 'Параметр id=% не найден', p_id;
    END IF;
    IF p_name        IS NOT NULL THEN UPDATE param_definition SET name=p_name         WHERE id=p_id; END IF;
    IF p_description IS NOT NULL THEN UPDATE param_definition SET description=p_description WHERE id=p_id; END IF;
    IF p_unit        IS NOT NULL THEN UPDATE param_definition SET unit=p_unit         WHERE id=p_id; END IF;
    IF p_min_value   IS NOT NULL THEN UPDATE param_definition SET min_value=p_min_value WHERE id=p_id; END IF;
    IF p_max_value   IS NOT NULL THEN UPDATE param_definition SET max_value=p_max_value WHERE id=p_id; END IF;
    IF p_is_required IS NOT NULL THEN UPDATE param_definition SET is_required=p_is_required WHERE id=p_id; END IF;
END;
$$ LANGUAGE plpgsql;

-- 3. Удалить определение параметра (каскадно удаляет значения)
CREATE OR REPLACE FUNCTION delete_param_definition(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM param_definition WHERE id=p_id) THEN
        RAISE EXCEPTION 'Параметр id=% не найден', p_id;
    END IF;
    DELETE FROM param_definition WHERE id=p_id;
END;
$$ LANGUAGE plpgsql;

-- 4. Назначить параметр категории
CREATE OR REPLACE FUNCTION assign_param_to_category(
    p_category_id INTEGER,
    p_param_id    INTEGER,
    p_is_inherited BOOLEAN DEFAULT TRUE,
    p_sort_order   INTEGER DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM category WHERE id=p_category_id) THEN
        RAISE EXCEPTION 'Категория id=% не найдена', p_category_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM param_definition WHERE id=p_param_id) THEN
        RAISE EXCEPTION 'Параметр id=% не найден', p_param_id;
    END IF;
    INSERT INTO category_param (category_id, param_id, is_inherited, sort_order)
    VALUES (p_category_id, p_param_id, p_is_inherited, p_sort_order)
    ON CONFLICT (category_id, param_id) DO UPDATE
        SET is_inherited=EXCLUDED.is_inherited, sort_order=EXCLUDED.sort_order;
END;
$$ LANGUAGE plpgsql;

-- 5. Снять параметр с категории
CREATE OR REPLACE FUNCTION remove_param_from_category(p_category_id INTEGER, p_param_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM category_param WHERE category_id=p_category_id AND param_id=p_param_id;
END;
$$ LANGUAGE plpgsql;

-- 6. Получить параметры категории с учётом наследования

CREATE OR REPLACE FUNCTION get_category_params(p_category_id INTEGER)
RETURNS TABLE (
    param_id             INTEGER,
    param_name           VARCHAR(255),
    description          TEXT,
    param_type           VARCHAR(20),
    unit                 VARCHAR(50),
    min_value            NUMERIC(15,4),
    max_value            NUMERIC(15,4),
    enum_class_id        INTEGER,
    enum_class_name      VARCHAR(100),
    is_required          BOOLEAN,
    is_inherited         BOOLEAN,
    source_category_id   INTEGER,
    source_category_name VARCHAR(255),
    sort_order           INTEGER
) AS $$
BEGIN
    RETURN QUERY
    -- Оборачиваем UNION ALL в подзапрос: это единственный способ использовать
    -- ORDER BY с именами колонок после UNION/INTERSECT/EXCEPT в PostgreSQL
    SELECT combined.*
    FROM (
        WITH RECURSIVE ancestors AS (
            SELECT c.id, c.name, c."Category_id", 0 AS depth
            FROM category c WHERE c.id = p_category_id
            UNION ALL
            SELECT c.id, c.name, c."Category_id", a.depth + 1
            FROM category c JOIN ancestors a ON c.id = a."Category_id"
        ),
        own_params AS (
            SELECT
                pd.id                                                         AS param_id,
                pd.name                                                       AS param_name,
                pd.description                                                AS description,
                pd.param_type                                                 AS param_type,
                pd.unit                                                       AS unit,
                pd.min_value                                                  AS min_value,
                pd.max_value                                                  AS max_value,
                pd.enum_class_id                                              AS enum_class_id,
                ec.name                                                       AS enum_class_name,
                pd.is_required                                                AS is_required,
                FALSE                                                         AS is_inherited,
                p_category_id                                                 AS source_category_id,
                (SELECT c2.name FROM category c2 WHERE c2.id = p_category_id) AS source_category_name,
                cp.sort_order                                                 AS sort_order
            FROM category_param cp
            JOIN param_definition pd ON pd.id = cp.param_id
            LEFT JOIN enum_class ec  ON ec.id  = pd.enum_class_id
            WHERE cp.category_id = p_category_id
        ),
        ancestor_params AS (
            SELECT
                pd.id          AS param_id,
                pd.name        AS param_name,
                pd.description AS description,
                pd.param_type  AS param_type,
                pd.unit        AS unit,
                pd.min_value   AS min_value,
                pd.max_value   AS max_value,
                pd.enum_class_id AS enum_class_id,
                ec.name        AS enum_class_name,
                pd.is_required AS is_required,
                TRUE           AS is_inherited,
                a.id           AS source_category_id,
                a.name         AS source_category_name,
                cp.sort_order  AS sort_order
            FROM ancestors a
            JOIN category_param cp ON cp.category_id = a.id AND cp.is_inherited = TRUE
            JOIN param_definition pd ON pd.id = cp.param_id
            LEFT JOIN enum_class ec  ON ec.id  = pd.enum_class_id
            WHERE a.id <> p_category_id
              AND cp.param_id NOT IN (
                  SELECT cp2.param_id FROM category_param cp2
                  WHERE cp2.category_id = p_category_id
              )
        )
        SELECT * FROM own_params
        UNION ALL
        SELECT * FROM ancestor_params
    ) combined
    ORDER BY combined.is_inherited, combined.sort_order, combined.param_name;
END;
$$ LANGUAGE plpgsql;

-- 7. Получить список всех определений параметров
CREATE OR REPLACE FUNCTION get_all_param_definitions()
RETURNS TABLE (
    id INTEGER, name VARCHAR(255), description TEXT, param_type VARCHAR(20),
    unit VARCHAR(50), min_value NUMERIC(15,4), max_value NUMERIC(15,4),
    enum_class_id INTEGER, enum_class_name VARCHAR(100), is_required BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT pd.id, pd.name, pd.description, pd.param_type, pd.unit,
           pd.min_value, pd.max_value, pd.enum_class_id, ec.name, pd.is_required
    FROM param_definition pd LEFT JOIN enum_class ec ON ec.id=pd.enum_class_id
    ORDER BY pd.name;
END;
$$ LANGUAGE plpgsql;

-- 8. Установить числовое значение параметра изделия (с проверкой ограничений)
CREATE OR REPLACE FUNCTION set_product_param_numeric(
    p_product_id INTEGER,
    p_param_id   INTEGER,
    p_value      NUMERIC(15,4)
) RETURNS VOID AS $$
DECLARE
    v_min NUMERIC(15,4); v_max NUMERIC(15,4); v_type VARCHAR(20);
BEGIN
    SELECT param_type, min_value, max_value INTO v_type, v_min, v_max
    FROM param_definition WHERE id=p_param_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Параметр id=% не найден', p_param_id; END IF;
    IF v_type <> 'numeric' THEN RAISE EXCEPTION 'Параметр id=% не является числовым', p_param_id; END IF;
    IF v_min IS NOT NULL AND p_value < v_min THEN
        RAISE EXCEPTION 'Значение % меньше минимально допустимого %', p_value, v_min;
    END IF;
    IF v_max IS NOT NULL AND p_value > v_max THEN
        RAISE EXCEPTION 'Значение % превышает максимально допустимое %', p_value, v_max;
    END IF;
    INSERT INTO product_param_numeric (product_id, param_id, value)
    VALUES (p_product_id, p_param_id, p_value)
    ON CONFLICT (product_id, param_id) DO UPDATE SET value=EXCLUDED.value;
END;
$$ LANGUAGE plpgsql;

-- 9. Установить enum-значение параметра изделия
CREATE OR REPLACE FUNCTION set_product_param_enum(
    p_product_id    INTEGER,
    p_param_id      INTEGER,
    p_enum_value_id INTEGER
) RETURNS VOID AS $$
DECLARE v_type VARCHAR(20); v_class_id INTEGER; v_ev_class_id INTEGER;
BEGIN
    SELECT param_type, enum_class_id INTO v_type, v_class_id FROM param_definition WHERE id=p_param_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Параметр id=% не найден', p_param_id; END IF;
    IF v_type <> 'enum' THEN RAISE EXCEPTION 'Параметр id=% не является перечислением', p_param_id; END IF;
    SELECT enum_class_id INTO v_ev_class_id FROM enum_value WHERE id=p_enum_value_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Значение перечисления id=% не найдено', p_enum_value_id; END IF;
    IF v_ev_class_id <> v_class_id THEN
        RAISE EXCEPTION 'Значение id=% принадлежит другому перечислению', p_enum_value_id;
    END IF;
    INSERT INTO product_param_enum (product_id, param_id, enum_value_id)
    VALUES (p_product_id, p_param_id, p_enum_value_id)
    ON CONFLICT (product_id, param_id) DO UPDATE SET enum_value_id=EXCLUDED.enum_value_id;
END;
$$ LANGUAGE plpgsql;

-- 10. Удалить значение параметра изделия
CREATE OR REPLACE FUNCTION delete_product_param(p_product_id INTEGER, p_param_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM product_param_numeric WHERE product_id=p_product_id AND param_id=p_param_id;
    DELETE FROM product_param_enum    WHERE product_id=p_product_id AND param_id=p_param_id;
END;
$$ LANGUAGE plpgsql;

-- 11. Получить все параметры и их значения для конкретного изделия
CREATE OR REPLACE FUNCTION get_product_params(p_product_id INTEGER)
RETURNS TABLE (
    param_id        INTEGER,
    param_name      VARCHAR(255),
    param_type      VARCHAR(20),
    unit            VARCHAR(50),
    min_value       NUMERIC(15,4),
    max_value       NUMERIC(15,4),
    numeric_value   NUMERIC(15,4),
    enum_value_id   INTEGER,
    enum_value_text VARCHAR(255),
    is_required     BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH product_cat AS (
        SELECT "Category_id" FROM product WHERE id=p_product_id
    ),
    -- все параметры применимые к категории изделия (с наследованием)
    applicable AS (
        SELECT gcp.param_id, gcp.param_name, gcp.param_type, gcp.unit,
               gcp.min_value, gcp.max_value, gcp.is_required
        FROM get_category_params((SELECT "Category_id" FROM product_cat)) gcp
    )
    SELECT
        ap.param_id, ap.param_name, ap.param_type, ap.unit, ap.min_value, ap.max_value,
        ppn.value             AS numeric_value,
        ppe.enum_value_id     AS enum_value_id,
        ev.value              AS enum_value_text,
        ap.is_required
    FROM applicable ap
    LEFT JOIN product_param_numeric ppn ON ppn.product_id=p_product_id AND ppn.param_id=ap.param_id
    LEFT JOIN product_param_enum    ppe ON ppe.product_id=p_product_id AND ppe.param_id=ap.param_id
    LEFT JOIN enum_value ev             ON ev.id = ppe.enum_value_id
    ORDER BY ap.param_name;
END;
$$ LANGUAGE plpgsql;

-- 12. Получить агрегаты числового параметра для категории (с учётом потомков)
CREATE OR REPLACE FUNCTION get_param_aggregates(p_category_id INTEGER, p_param_id INTEGER)
RETURNS TABLE (
    param_id    INTEGER,
    param_name  VARCHAR(255),
    unit        VARCHAR(50),
    cnt         BIGINT,
    min_val     NUMERIC(15,4),
    max_val     NUMERIC(15,4),
    avg_val     NUMERIC(15,4),
    sum_val     NUMERIC(15,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE subtree AS (
        SELECT id FROM category WHERE id=p_category_id
        UNION ALL
        SELECT c.id FROM category c JOIN subtree s ON c."Category_id"=s.id
    )
    SELECT
        pd.id, pd.name, pd.unit,
        COUNT(ppn.value)::BIGINT,
        MIN(ppn.value), MAX(ppn.value),
        ROUND(AVG(ppn.value),4), SUM(ppn.value)
    FROM param_definition pd
    LEFT JOIN product_param_numeric ppn ON ppn.param_id=pd.id
    LEFT JOIN product p ON p.id=ppn.product_id AND p."Category_id" IN (SELECT id FROM subtree)
    WHERE pd.id=p_param_id AND pd.param_type='numeric'
    GROUP BY pd.id, pd.name, pd.unit;
END;
$$ LANGUAGE plpgsql;

-- 13. Поиск изделий в категории (с потомками) по значениям параметров
--     Принимает диапазон числового параметра и/или список enum_value_id
CREATE OR REPLACE FUNCTION search_products_by_params(
    p_category_id   INTEGER,
    p_param_id      INTEGER,
    p_num_min       NUMERIC(15,4) DEFAULT NULL,
    p_num_max       NUMERIC(15,4) DEFAULT NULL,
    p_enum_value_id INTEGER       DEFAULT NULL
) RETURNS TABLE (
    product_id   INTEGER,
    product_name VARCHAR(255),
    category_id  INTEGER,
    category_name VARCHAR(255),
    price        NUMERIC(10,2),
    brand        VARCHAR(200)
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE subtree AS (
        SELECT id FROM category WHERE id=p_category_id
        UNION ALL
        SELECT c.id FROM category c JOIN subtree s ON c."Category_id"=s.id
    )
    SELECT DISTINCT p.id, p.name, p."Category_id", cat.name, p.price, p.brand
    FROM product p
    JOIN category cat ON cat.id = p."Category_id"
    WHERE p."Category_id" IN (SELECT id FROM subtree)
      AND (
          -- числовой фильтр
          (p_enum_value_id IS NULL AND EXISTS (
              SELECT 1 FROM product_param_numeric ppn
              WHERE ppn.product_id=p.id AND ppn.param_id=p_param_id
                AND (p_num_min IS NULL OR ppn.value >= p_num_min)
                AND (p_num_max IS NULL OR ppn.value <= p_num_max)
          ))
          OR
          -- enum-фильтр
          (p_num_min IS NULL AND p_num_max IS NULL AND EXISTS (
              SELECT 1 FROM product_param_enum ppe
              WHERE ppe.product_id=p.id AND ppe.param_id=p_param_id
                AND (p_enum_value_id IS NULL OR ppe.enum_value_id=p_enum_value_id)
          ))
      )
    ORDER BY p.name;
END;
$$ LANGUAGE plpgsql;

-- 14. Получить все параметры, назначенные категории (без наследования)
CREATE OR REPLACE FUNCTION get_direct_category_params(p_category_id INTEGER)
RETURNS TABLE (
    param_id     INTEGER,
    param_name   VARCHAR(255),
    param_type   VARCHAR(20),
    unit         VARCHAR(50),
    min_value    NUMERIC(15,4),
    max_value    NUMERIC(15,4),
    enum_class_id INTEGER,
    is_required  BOOLEAN,
    is_inherited BOOLEAN,
    sort_order   INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT pd.id, pd.name, pd.param_type, pd.unit, pd.min_value, pd.max_value,
           pd.enum_class_id, pd.is_required, cp.is_inherited, cp.sort_order
    FROM category_param cp
    JOIN param_definition pd ON pd.id=cp.param_id
    WHERE cp.category_id=p_category_id
    ORDER BY cp.sort_order, pd.name;
END;
$$ LANGUAGE plpgsql;


-- =============================================
-- ХОЗЯЙСТВЕННЫЕ ОПЕРАЦИИ (ХО)
-- Расширение основной модели данных каталога
-- =============================================

-- Классификатор классов ХО (иерархия)
CREATE TABLE xo_class (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id   INTEGER REFERENCES xo_class(id) ON DELETE RESTRICT,
    sort_order  INTEGER DEFAULT 0
);

COMMENT ON TABLE xo_class IS
    'Классификатор хозяйственных операций. Поддерживает иерархию классов.';
COMMENT ON COLUMN xo_class.parent_id IS
    'Родительский класс ХО. NULL — корневой класс.';

CREATE INDEX idx_xo_class_parent ON xo_class(parent_id);

-- Назначение параметров классам ХО
-- Повторно использует param_definition из общего справочника параметров
CREATE TABLE xo_param_def (
    id           SERIAL PRIMARY KEY,
    xo_class_id  INTEGER NOT NULL REFERENCES xo_class(id) ON DELETE CASCADE,
    param_def_id INTEGER NOT NULL REFERENCES param_definition(id) ON DELETE CASCADE,
    is_inherited BOOLEAN DEFAULT TRUE,
    sort_order   INTEGER DEFAULT 0,
    UNIQUE(xo_class_id, param_def_id)
);

COMMENT ON TABLE xo_param_def IS
    'Назначение параметров классам ХО. is_inherited=TRUE — параметр передаётся подклассам.';

CREATE INDEX idx_xo_param_def_class ON xo_param_def(xo_class_id);

-- Определения ролей для классов ХО
CREATE TABLE xo_role_def (
    id           SERIAL PRIMARY KEY,
    xo_class_id  INTEGER NOT NULL REFERENCES xo_class(id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    description  TEXT,
    is_required  BOOLEAN DEFAULT TRUE,
    subject_type VARCHAR(50)  -- 'organization', 'person', 'warehouse', 'any'
);

COMMENT ON TABLE xo_role_def IS
    'Определения ролей участников для каждого класса ХО (Поставщик, Покупатель, МОЛ и т.д.)';

CREATE INDEX idx_xo_role_def_class ON xo_role_def(xo_class_id);

-- Экземпляры хозяйственных операций
CREATE TABLE xo_instance (
    id          SERIAL PRIMARY KEY,
    xo_class_id INTEGER NOT NULL REFERENCES xo_class(id) ON DELETE RESTRICT,
    number      VARCHAR(50),
    op_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    status      VARCHAR(20) NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'posted', 'cancelled')),
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by  VARCHAR(100)
);

COMMENT ON TABLE xo_instance IS
    'Экземпляры хозяйственных операций — конкретные документированные факты хоз. деятельности.';
COMMENT ON COLUMN xo_instance.status IS
    'draft — черновик, posted — проведён, cancelled — отменён';

CREATE INDEX idx_xo_instance_class  ON xo_instance(xo_class_id);
CREATE INDEX idx_xo_instance_date   ON xo_instance(op_date);
CREATE INDEX idx_xo_instance_status ON xo_instance(status);

-- Значения параметров экземпляров ХО (EAV-модель)
CREATE TABLE xo_param_value (
    id            SERIAL PRIMARY KEY,
    xo_id         INTEGER NOT NULL REFERENCES xo_instance(id) ON DELETE CASCADE,
    param_def_id  INTEGER NOT NULL REFERENCES param_definition(id) ON DELETE CASCADE,
    numeric_value NUMERIC(15,4),
    text_value    TEXT,
    enum_value_id INTEGER REFERENCES enum_value(id) ON DELETE SET NULL,
    UNIQUE(xo_id, param_def_id)
);

COMMENT ON TABLE xo_param_value IS
    'Значения параметров конкретных экземпляров ХО (EAV-паттерн).';

CREATE INDEX idx_xo_param_value_xo    ON xo_param_value(xo_id);
CREATE INDEX idx_xo_param_value_param ON xo_param_value(param_def_id);

-- Назначение ролей в экземплярах ХО
CREATE TABLE xo_role_assign (
    id           SERIAL PRIMARY KEY,
    xo_id        INTEGER NOT NULL REFERENCES xo_instance(id) ON DELETE CASCADE,
    role_def_id  INTEGER NOT NULL REFERENCES xo_role_def(id) ON DELETE CASCADE,
    subject_id   INTEGER,
    subject_type VARCHAR(50),
    subject_name VARCHAR(255) NOT NULL
);

COMMENT ON TABLE xo_role_assign IS
    'Назначение конкретных субъектов на роли в экземплярах ХО.';

CREATE INDEX idx_xo_role_assign_xo   ON xo_role_assign(xo_id);
CREATE INDEX idx_xo_role_assign_role ON xo_role_assign(role_def_id);

-- Строки (табличная часть) экземпляров ХО
CREATE TABLE xo_line (
    id         SERIAL PRIMARY KEY,
    xo_id      INTEGER NOT NULL REFERENCES xo_instance(id) ON DELETE CASCADE,
    line_order INTEGER NOT NULL,
    product_id INTEGER REFERENCES product(id) ON DELETE RESTRICT,
    quantity   NUMERIC(15,4) NOT NULL CHECK (quantity > 0),
    price      NUMERIC(10,2),
    unit_name  VARCHAR(50)
);

COMMENT ON TABLE xo_line IS
    'Строки табличной части ХО (позиции товаров/услуг).';

CREATE INDEX idx_xo_line_xo      ON xo_line(xo_id);
CREATE INDEX idx_xo_line_product ON xo_line(product_id);

-- =============================================
-- SQL-ПРОЦЕДУРЫ ДЛЯ РАБОТЫ С КЛАССАМИ ХО
-- =============================================

-- 1. Создать класс ХО
CREATE OR REPLACE FUNCTION add_xo_class(
    p_name        VARCHAR(255),
    p_description TEXT    DEFAULT NULL,
    p_parent_id   INTEGER DEFAULT NULL,
    p_sort_order  INTEGER DEFAULT 0
) RETURNS INTEGER AS $$
DECLARE new_id INTEGER;
BEGIN
    IF p_parent_id IS NOT NULL AND
       NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_parent_id) THEN
        RAISE EXCEPTION 'Родительский класс ХО id=% не найден', p_parent_id;
    END IF;
    INSERT INTO xo_class(name, description, parent_id, sort_order)
    VALUES (p_name, p_description, p_parent_id, p_sort_order)
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION add_xo_class IS 'Создать новый класс ХО в классификаторе.';

-- 2. Обновить класс ХО
CREATE OR REPLACE FUNCTION update_xo_class(
    p_id          INTEGER,
    p_name        VARCHAR(255) DEFAULT NULL,
    p_description TEXT         DEFAULT NULL,
    p_sort_order  INTEGER      DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_id) THEN
        RAISE EXCEPTION 'Класс ХО id=% не найден', p_id;
    END IF;
    IF p_name        IS NOT NULL THEN UPDATE xo_class SET name        = p_name        WHERE id = p_id; END IF;
    IF p_description IS NOT NULL THEN UPDATE xo_class SET description = p_description WHERE id = p_id; END IF;
    IF p_sort_order  IS NOT NULL THEN UPDATE xo_class SET sort_order  = p_sort_order  WHERE id = p_id; END IF;
END;
$$ LANGUAGE plpgsql;

-- 3. Удалить класс ХО (только если нет экземпляров)
CREATE OR REPLACE FUNCTION delete_xo_class(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_id) THEN
        RAISE EXCEPTION 'Класс ХО id=% не найден', p_id;
    END IF;
    IF EXISTS (SELECT 1 FROM xo_instance WHERE xo_class_id = p_id) THEN
        RAISE EXCEPTION 'Невозможно удалить класс ХО id=%: существуют экземпляры', p_id;
    END IF;
    IF EXISTS (SELECT 1 FROM xo_class WHERE parent_id = p_id) THEN
        RAISE EXCEPTION 'Невозможно удалить класс ХО id=%: есть дочерние классы', p_id;
    END IF;
    DELETE FROM xo_class WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- 4. Переместить класс ХО в другой родитель
CREATE OR REPLACE FUNCTION move_xo_class(p_id INTEGER, p_new_parent_id INTEGER DEFAULT NULL) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_id) THEN
        RAISE EXCEPTION 'Класс ХО id=% не найден', p_id;
    END IF;
    IF p_new_parent_id IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_new_parent_id) THEN
            RAISE EXCEPTION 'Новый родительский класс id=% не найден', p_new_parent_id;
        END IF;
        -- Проверка цикла
        IF p_new_parent_id = p_id THEN
            RAISE EXCEPTION 'Класс не может быть родителем самого себя';
        END IF;
    END IF;
    UPDATE xo_class SET parent_id = p_new_parent_id WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- 5. Назначить параметр классу ХО
CREATE OR REPLACE FUNCTION assign_param_to_xo_class(
    p_xo_class_id  INTEGER,
    p_param_def_id INTEGER,
    p_is_inherited BOOLEAN DEFAULT TRUE,
    p_sort_order   INTEGER DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_xo_class_id) THEN
        RAISE EXCEPTION 'Класс ХО id=% не найден', p_xo_class_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM param_definition WHERE id = p_param_def_id) THEN
        RAISE EXCEPTION 'Определение параметра id=% не найдено', p_param_def_id;
    END IF;
    INSERT INTO xo_param_def(xo_class_id, param_def_id, is_inherited, sort_order)
    VALUES (p_xo_class_id, p_param_def_id, p_is_inherited, p_sort_order)
    ON CONFLICT (xo_class_id, param_def_id)
    DO UPDATE SET is_inherited = EXCLUDED.is_inherited,
                  sort_order   = EXCLUDED.sort_order;
END;
$$ LANGUAGE plpgsql;

-- 6. Снять параметр с класса ХО
CREATE OR REPLACE FUNCTION remove_param_from_xo_class(
    p_xo_class_id  INTEGER,
    p_param_def_id INTEGER
) RETURNS VOID AS $$
BEGIN
    DELETE FROM xo_param_def
    WHERE xo_class_id = p_xo_class_id AND param_def_id = p_param_def_id;
END;
$$ LANGUAGE plpgsql;

-- 7. Добавить определение роли к классу ХО
CREATE OR REPLACE FUNCTION add_xo_role_def(
    p_xo_class_id  INTEGER,
    p_name         VARCHAR(100),
    p_description  TEXT         DEFAULT NULL,
    p_is_required  BOOLEAN      DEFAULT TRUE,
    p_subject_type VARCHAR(50)  DEFAULT 'any'
) RETURNS INTEGER AS $$
DECLARE new_id INTEGER;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_xo_class_id) THEN
        RAISE EXCEPTION 'Класс ХО id=% не найден', p_xo_class_id;
    END IF;
    INSERT INTO xo_role_def(xo_class_id, name, description, is_required, subject_type)
    VALUES (p_xo_class_id, p_name, p_description, p_is_required, p_subject_type)
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- 8. Удалить определение роли
CREATE OR REPLACE FUNCTION delete_xo_role_def(p_role_def_id INTEGER) RETURNS VOID AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM xo_role_assign WHERE role_def_id = p_role_def_id) THEN
        RAISE EXCEPTION 'Нельзя удалить роль id=%: используется в экземплярах ХО', p_role_def_id;
    END IF;
    DELETE FROM xo_role_def WHERE id = p_role_def_id;
END;
$$ LANGUAGE plpgsql;

-- 9. Получить шаблон класса ХО (параметры с учётом наследования от родителей)
CREATE OR REPLACE FUNCTION get_xo_class_template(p_xo_class_id INTEGER)
RETURNS TABLE (
    param_def_id      INTEGER,
    param_name        VARCHAR(255),
    param_type        VARCHAR(20),
    unit              VARCHAR(50),
    min_value         NUMERIC(15,4),
    max_value         NUMERIC(15,4),
    enum_class_id     INTEGER,
    enum_class_name   VARCHAR(100),
    is_required       BOOLEAN,
    is_inherited_xo   BOOLEAN,
    source_class_id   INTEGER,
    source_class_name VARCHAR(255),
    sort_order        INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT combined.*
    FROM (
        WITH RECURSIVE xo_ancestors AS (
            SELECT xc.id, xc.name, xc.parent_id, 0 AS depth
            FROM xo_class xc WHERE xc.id = p_xo_class_id
            UNION ALL
            SELECT xc.id, xc.name, xc.parent_id, xa.depth + 1
            FROM xo_class xc JOIN xo_ancestors xa ON xc.id = xa.parent_id
        ),
        own_params AS (
            SELECT
                pd.id           AS param_def_id,
                pd.name         AS param_name,
                pd.param_type,
                pd.unit,
                pd.min_value,
                pd.max_value,
                pd.enum_class_id,
                ec.name         AS enum_class_name,
                pd.is_required,
                FALSE           AS is_inherited_xo,
                p_xo_class_id  AS source_class_id,
                (SELECT xc2.name FROM xo_class xc2 WHERE xc2.id = p_xo_class_id) AS source_class_name,
                xpd.sort_order
            FROM xo_param_def xpd
            JOIN param_definition pd ON pd.id = xpd.param_def_id
            LEFT JOIN enum_class ec  ON ec.id  = pd.enum_class_id
            WHERE xpd.xo_class_id = p_xo_class_id
        ),
        inherited_params AS (
            SELECT
                pd.id           AS param_def_id,
                pd.name         AS param_name,
                pd.param_type,
                pd.unit,
                pd.min_value,
                pd.max_value,
                pd.enum_class_id,
                ec.name         AS enum_class_name,
                pd.is_required,
                TRUE            AS is_inherited_xo,
                a.id            AS source_class_id,
                a.name          AS source_class_name,
                xpd.sort_order
            FROM xo_ancestors a
            JOIN xo_param_def xpd ON xpd.xo_class_id = a.id AND xpd.is_inherited = TRUE
            JOIN param_definition pd ON pd.id = xpd.param_def_id
            LEFT JOIN enum_class ec  ON ec.id  = pd.enum_class_id
            WHERE a.id <> p_xo_class_id
              AND xpd.param_def_id NOT IN (
                  SELECT xpd2.param_def_id FROM xo_param_def xpd2
                  WHERE xpd2.xo_class_id = p_xo_class_id
              )
        )
        SELECT * FROM own_params
        UNION ALL
        SELECT * FROM inherited_params
    ) combined
    ORDER BY combined.is_inherited_xo, combined.sort_order, combined.param_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_xo_class_template IS
    'Возвращает полный шаблон класса ХО: собственные параметры + унаследованные от предков.';

-- 10. Получить роли класса ХО
CREATE OR REPLACE FUNCTION get_xo_class_roles(p_xo_class_id INTEGER)
RETURNS TABLE (
    id           INTEGER,
    name         VARCHAR(100),
    description  TEXT,
    is_required  BOOLEAN,
    subject_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT rd.id, rd.name, rd.description, rd.is_required, rd.subject_type
    FROM xo_role_def rd
    WHERE rd.xo_class_id = p_xo_class_id
    ORDER BY rd.name;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- SQL-ПРОЦЕДУРЫ ДЛЯ РАБОТЫ С ЭКЗЕМПЛЯРАМИ ХО
-- =============================================

-- 11. Создать экземпляр ХО
CREATE OR REPLACE FUNCTION create_xo_instance(
    p_xo_class_id INTEGER,
    p_number      VARCHAR(50)  DEFAULT NULL,
    p_op_date     DATE         DEFAULT CURRENT_DATE,
    p_notes       TEXT         DEFAULT NULL,
    p_created_by  VARCHAR(100) DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE new_id INTEGER;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM xo_class WHERE id = p_xo_class_id) THEN
        RAISE EXCEPTION 'Класс ХО id=% не найден', p_xo_class_id;
    END IF;
    INSERT INTO xo_instance(xo_class_id, number, op_date, status, notes, created_by)
    VALUES (p_xo_class_id, p_number, p_op_date, 'draft', p_notes, p_created_by)
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- 12. Обновить экземпляр ХО (только в статусе draft)
CREATE OR REPLACE FUNCTION update_xo_instance(
    p_xo_id   INTEGER,
    p_number  VARCHAR(50) DEFAULT NULL,
    p_op_date DATE        DEFAULT NULL,
    p_notes   TEXT        DEFAULT NULL
) RETURNS VOID AS $$
DECLARE v_status VARCHAR(20);
BEGIN
    SELECT status INTO v_status FROM xo_instance WHERE id = p_xo_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Экземпляр ХО id=% не найден', p_xo_id;
    END IF;
    IF v_status <> 'draft' THEN
        RAISE EXCEPTION 'Нельзя редактировать ХО в статусе %. Только draft.', v_status;
    END IF;
    IF p_number  IS NOT NULL THEN UPDATE xo_instance SET number  = p_number  WHERE id = p_xo_id; END IF;
    IF p_op_date IS NOT NULL THEN UPDATE xo_instance SET op_date = p_op_date WHERE id = p_xo_id; END IF;
    IF p_notes   IS NOT NULL THEN UPDATE xo_instance SET notes   = p_notes   WHERE id = p_xo_id; END IF;
END;
$$ LANGUAGE plpgsql;

-- 13. Установить значение параметра ХО (с проверкой ограничений)
CREATE OR REPLACE FUNCTION set_xo_param_value(
    p_xo_id        INTEGER,
    p_param_def_id INTEGER,
    p_num_value    NUMERIC(15,4) DEFAULT NULL,
    p_text_value   TEXT          DEFAULT NULL,
    p_enum_val_id  INTEGER       DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_type    VARCHAR(20);
    v_min     NUMERIC(15,4);
    v_max     NUMERIC(15,4);
    v_cls_id  INTEGER;
    v_ev_cls  INTEGER;
    v_status  VARCHAR(20);
BEGIN
    SELECT status INTO v_status FROM xo_instance WHERE id = p_xo_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Экземпляр ХО id=% не найден', p_xo_id;
    END IF;
    IF v_status <> 'draft' THEN
        RAISE EXCEPTION 'Нельзя изменять параметры ХО в статусе %', v_status;
    END IF;

    SELECT param_type, min_value, max_value, enum_class_id
    INTO v_type, v_min, v_max, v_cls_id
    FROM param_definition WHERE id = p_param_def_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Параметр id=% не найден', p_param_def_id;
    END IF;

    -- Проверка числовых ограничений
    IF v_type = 'numeric' AND p_num_value IS NOT NULL THEN
        IF v_min IS NOT NULL AND p_num_value < v_min THEN
            RAISE EXCEPTION 'Значение % меньше минимально допустимого %', p_num_value, v_min;
        END IF;
        IF v_max IS NOT NULL AND p_num_value > v_max THEN
            RAISE EXCEPTION 'Значение % превышает максимально допустимое %', p_num_value, v_max;
        END IF;
    END IF;

    -- Проверка принадлежности enum-значения
    IF v_type = 'enum' AND p_enum_val_id IS NOT NULL THEN
        SELECT enum_class_id INTO v_ev_cls FROM enum_value WHERE id = p_enum_val_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Значение перечисления id=% не найдено', p_enum_val_id;
        END IF;
        IF v_ev_cls <> v_cls_id THEN
            RAISE EXCEPTION 'Значение id=% принадлежит другому перечислению', p_enum_val_id;
        END IF;
    END IF;

    INSERT INTO xo_param_value(xo_id, param_def_id, numeric_value, text_value, enum_value_id)
    VALUES (p_xo_id, p_param_def_id, p_num_value, p_text_value, p_enum_val_id)
    ON CONFLICT (xo_id, param_def_id)
    DO UPDATE SET numeric_value = EXCLUDED.numeric_value,
                  text_value    = EXCLUDED.text_value,
                  enum_value_id = EXCLUDED.enum_value_id;
END;
$$ LANGUAGE plpgsql;

-- 14. Назначить роль в экземпляре ХО
CREATE OR REPLACE FUNCTION assign_xo_role(
    p_xo_id        INTEGER,
    p_role_def_id  INTEGER,
    p_subject_name VARCHAR(255),
    p_subject_id   INTEGER     DEFAULT NULL,
    p_subject_type VARCHAR(50) DEFAULT NULL
) RETURNS VOID AS $$
DECLARE v_status VARCHAR(20);
BEGIN
    SELECT status INTO v_status FROM xo_instance WHERE id = p_xo_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Экземпляр ХО id=% не найден', p_xo_id; END IF;
    IF v_status <> 'draft' THEN
        RAISE EXCEPTION 'Нельзя изменять роли ХО в статусе %', v_status;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM xo_role_def WHERE id = p_role_def_id) THEN
        RAISE EXCEPTION 'Определение роли id=% не найдено', p_role_def_id;
    END IF;
    -- Upsert по xo_id + role_def_id
    DELETE FROM xo_role_assign WHERE xo_id = p_xo_id AND role_def_id = p_role_def_id;
    INSERT INTO xo_role_assign(xo_id, role_def_id, subject_id, subject_type, subject_name)
    VALUES (p_xo_id, p_role_def_id, p_subject_id, p_subject_type, p_subject_name);
END;
$$ LANGUAGE plpgsql;

-- 15. Добавить строку в табличную часть ХО
CREATE OR REPLACE FUNCTION add_xo_line(
    p_xo_id      INTEGER,
    p_product_id INTEGER,
    p_quantity   NUMERIC(15,4),
    p_price      NUMERIC(10,2) DEFAULT NULL,
    p_unit_name  VARCHAR(50)   DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE new_id INTEGER; max_order INTEGER; v_status VARCHAR(20);
BEGIN
    SELECT status INTO v_status FROM xo_instance WHERE id = p_xo_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Экземпляр ХО id=% не найден', p_xo_id; END IF;
    IF v_status <> 'draft' THEN
        RAISE EXCEPTION 'Нельзя добавлять строки в ХО в статусе %', v_status;
    END IF;
    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Количество должно быть > 0, получено %', p_quantity;
    END IF;
    IF p_product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM product WHERE id = p_product_id) THEN
        RAISE EXCEPTION 'Товар id=% не найден', p_product_id;
    END IF;
    SELECT COALESCE(MAX(line_order), 0) + 1 INTO max_order
    FROM xo_line WHERE xo_id = p_xo_id;
    INSERT INTO xo_line(xo_id, line_order, product_id, quantity, price, unit_name)
    VALUES (p_xo_id, max_order, p_product_id, p_quantity, p_price, p_unit_name)
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- 16. Удалить строку из табличной части
CREATE OR REPLACE FUNCTION delete_xo_line(p_line_id INTEGER) RETURNS VOID AS $$
DECLARE v_xo_id INTEGER; v_status VARCHAR(20);
BEGIN
    SELECT xo_id INTO v_xo_id FROM xo_line WHERE id = p_line_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Строка ХО id=% не найдена', p_line_id; END IF;
    SELECT status INTO v_status FROM xo_instance WHERE id = v_xo_id;
    IF v_status <> 'draft' THEN
        RAISE EXCEPTION 'Нельзя удалять строки из ХО в статусе %', v_status;
    END IF;
    DELETE FROM xo_line WHERE id = p_line_id;
END;
$$ LANGUAGE plpgsql;

-- 17. Провести ХО (draft -> posted): проверяет обязательные роли
CREATE OR REPLACE FUNCTION post_xo(p_xo_id INTEGER) RETURNS VOID AS $$
DECLARE
    v_class_id   INTEGER;
    v_status     VARCHAR(20);
    missing_role VARCHAR(100);
BEGIN
    SELECT xo_class_id, status INTO v_class_id, v_status
    FROM xo_instance WHERE id = p_xo_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ХО id=% не найдена', p_xo_id;
    END IF;
    IF v_status <> 'draft' THEN
        RAISE EXCEPTION 'ХО id=% уже в статусе %. Провести можно только draft.', p_xo_id, v_status;
    END IF;
    -- Проверка обязательных ролей
    SELECT rd.name INTO missing_role
    FROM xo_role_def rd
    WHERE rd.xo_class_id = v_class_id AND rd.is_required = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM xo_role_assign ra
          WHERE ra.xo_id = p_xo_id AND ra.role_def_id = rd.id
      )
    LIMIT 1;
    IF missing_role IS NOT NULL THEN
        RAISE EXCEPTION 'Не заполнена обязательная роль: «%»', missing_role;
    END IF;
    UPDATE xo_instance SET status = 'posted' WHERE id = p_xo_id;
END;
$$ LANGUAGE plpgsql;

-- 18. Отменить ХО (posted -> cancelled)
CREATE OR REPLACE FUNCTION cancel_xo(p_xo_id INTEGER, p_reason TEXT DEFAULT NULL) RETURNS VOID AS $$
DECLARE v_status VARCHAR(20);
BEGIN
    SELECT status INTO v_status FROM xo_instance WHERE id = p_xo_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'ХО id=% не найдена', p_xo_id; END IF;
    IF v_status = 'cancelled' THEN
        RAISE EXCEPTION 'ХО id=% уже отменена', p_xo_id;
    END IF;
    UPDATE xo_instance
    SET status = 'cancelled',
        notes  = COALESCE(p_reason, notes)
    WHERE id = p_xo_id;
END;
$$ LANGUAGE plpgsql;

-- 19. Получить все значения параметров конкретного экземпляра ХО
CREATE OR REPLACE FUNCTION get_xo_params(p_xo_id INTEGER)
RETURNS TABLE (
    param_def_id    INTEGER,
    param_name      VARCHAR(255),
    param_type      VARCHAR(20),
    unit            VARCHAR(50),
    numeric_value   NUMERIC(15,4),
    text_value      TEXT,
    enum_value_id   INTEGER,
    enum_value_text VARCHAR(255)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pd.id, pd.name, pd.param_type, pd.unit,
        pv.numeric_value, pv.text_value,
        pv.enum_value_id, ev.value
    FROM xo_param_value pv
    JOIN param_definition pd ON pd.id = pv.param_def_id
    LEFT JOIN enum_value ev  ON ev.id  = pv.enum_value_id
    WHERE pv.xo_id = p_xo_id
    ORDER BY pd.name;
END;
$$ LANGUAGE plpgsql;

-- 20. Получить строки табличной части экземпляра ХО
CREATE OR REPLACE FUNCTION get_xo_lines(p_xo_id INTEGER)
RETURNS TABLE (
    line_id    INTEGER,
    line_order INTEGER,
    product_id INTEGER,
    product_name VARCHAR(255),
    quantity   NUMERIC(15,4),
    price      NUMERIC(10,2),
    amount     NUMERIC(15,2),
    unit_name  VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        xl.id, xl.line_order, xl.product_id, p.name,
        xl.quantity, xl.price,
        ROUND(xl.quantity * COALESCE(xl.price, 0), 2) AS amount,
        xl.unit_name
    FROM xo_line xl
    LEFT JOIN product p ON p.id = xl.product_id
    WHERE xl.xo_id = p_xo_id
    ORDER BY xl.line_order;
END;
$$ LANGUAGE plpgsql;

-- 21. Получить назначения ролей экземпляра ХО
CREATE OR REPLACE FUNCTION get_xo_roles(p_xo_id INTEGER)
RETURNS TABLE (
    role_def_id  INTEGER,
    role_name    VARCHAR(100),
    is_required  BOOLEAN,
    subject_name VARCHAR(255),
    subject_type VARCHAR(50),
    subject_id   INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT rd.id, rd.name, rd.is_required, ra.subject_name, ra.subject_type, ra.subject_id
    FROM xo_role_def rd
    JOIN xo_instance xi ON xi.xo_class_id = rd.xo_class_id AND xi.id = p_xo_id
    LEFT JOIN xo_role_assign ra ON ra.xo_id = p_xo_id AND ra.role_def_id = rd.id
    ORDER BY rd.name;
END;
$$ LANGUAGE plpgsql;

-- 22. Полное представление ХО (заголовок + роли + параметры)
CREATE OR REPLACE FUNCTION get_xo_full(p_xo_id INTEGER)
RETURNS TABLE (field_type VARCHAR(20), field_name VARCHAR(255), field_value TEXT) AS $$
BEGIN
    -- Заголовок
    RETURN QUERY
    SELECT 'header'::VARCHAR(20), 'Номер'::VARCHAR(255), xi.number::TEXT
    FROM xo_instance xi WHERE xi.id = p_xo_id;

    RETURN QUERY
    SELECT 'header'::VARCHAR(20), 'Класс ХО'::VARCHAR(255), xc.name::TEXT
    FROM xo_instance xi JOIN xo_class xc ON xc.id = xi.xo_class_id
    WHERE xi.id = p_xo_id;

    RETURN QUERY
    SELECT 'header'::VARCHAR(20), 'Дата'::VARCHAR(255), xi.op_date::TEXT
    FROM xo_instance xi WHERE xi.id = p_xo_id;

    RETURN QUERY
    SELECT 'header'::VARCHAR(20), 'Статус'::VARCHAR(255), xi.status::TEXT
    FROM xo_instance xi WHERE xi.id = p_xo_id;

    -- Роли
    RETURN QUERY
    SELECT 'role'::VARCHAR(20), rd.name::VARCHAR(255),
           COALESCE(ra.subject_name, '(не назначено)')::TEXT
    FROM xo_role_def rd
    JOIN xo_instance xi ON xi.xo_class_id = rd.xo_class_id AND xi.id = p_xo_id
    LEFT JOIN xo_role_assign ra ON ra.xo_id = p_xo_id AND ra.role_def_id = rd.id
    ORDER BY rd.name;

    -- Параметры
    RETURN QUERY
    SELECT 'param'::VARCHAR(20), pd.name::VARCHAR(255),
           CASE pd.param_type
               WHEN 'numeric' THEN COALESCE(pv.numeric_value::TEXT, '(не задано)')
                   || COALESCE(' ' || pd.unit, '')
               WHEN 'enum'    THEN COALESCE(ev.value::TEXT, '(не задано)')
               ELSE COALESCE(pv.text_value, '(не задано)')
           END
    FROM xo_param_value pv
    JOIN param_definition pd ON pd.id = pv.param_def_id
    LEFT JOIN enum_value ev  ON ev.id  = pv.enum_value_id
    WHERE pv.xo_id = p_xo_id
    ORDER BY pd.name;

    -- Строки (исправлено: явное приведение field_name к VARCHAR(255))
    RETURN QUERY
    SELECT 'line'::VARCHAR(20),
           ((ROW_NUMBER() OVER (ORDER BY xl.line_order))::TEXT || '. ' || COALESCE(p.name, 'Без товара')
           || ' x' || xl.quantity || COALESCE(' ' || xl.unit_name, ''))::VARCHAR(255),
           (COALESCE('Цена: ' || xl.price::TEXT || ', Сумма: '
               || ROUND(xl.quantity * COALESCE(xl.price, 0), 2)::TEXT, ''))::TEXT
    FROM xo_line xl
    LEFT JOIN product p ON p.id = xl.product_id
    WHERE xl.xo_id = p_xo_id
    ORDER BY xl.line_order;
END;
$$ LANGUAGE plpgsql;

-- 23. Поиск ХО по классу и диапазону числового параметра
CREATE OR REPLACE FUNCTION search_xo_by_param(
    p_xo_class_id  INTEGER,
    p_param_def_id INTEGER,
    p_num_min      NUMERIC(15,4) DEFAULT NULL,
    p_num_max      NUMERIC(15,4) DEFAULT NULL,
    p_enum_val_id  INTEGER       DEFAULT NULL,
    p_status       VARCHAR(20)   DEFAULT NULL
) RETURNS TABLE (
    xo_id       INTEGER,
    xo_number   VARCHAR(50),
    xo_class    VARCHAR(255),
    op_date     DATE,
    status      VARCHAR(20),
    param_name  VARCHAR(255),
    param_value TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE xo_subtree AS (
        SELECT id FROM xo_class WHERE id = p_xo_class_id
        UNION ALL
        SELECT xc.id FROM xo_class xc JOIN xo_subtree xs ON xc.parent_id = xs.id
    )
    SELECT DISTINCT xi.id, xi.number, xc.name, xi.op_date, xi.status,
           pd.name,
           CASE pd.param_type
               WHEN 'numeric' THEN pv.numeric_value::TEXT || COALESCE(' ' || pd.unit, '')
               WHEN 'enum'    THEN ev.value::TEXT
               ELSE pv.text_value
           END
    FROM xo_instance xi
    JOIN xo_class xc       ON xc.id = xi.xo_class_id
    JOIN xo_param_value pv ON pv.xo_id = xi.id
    JOIN param_definition pd ON pd.id = pv.param_def_id
    LEFT JOIN enum_value ev  ON ev.id  = pv.enum_value_id
    WHERE xi.xo_class_id IN (SELECT id FROM xo_subtree)
      AND pv.param_def_id = p_param_def_id
      AND (p_status IS NULL OR xi.status = p_status)
      AND (
          (p_enum_val_id IS NULL AND
           (p_num_min IS NULL OR pv.numeric_value >= p_num_min) AND
           (p_num_max IS NULL OR pv.numeric_value <= p_num_max))
          OR
          (p_enum_val_id IS NOT NULL AND pv.enum_value_id = p_enum_val_id)
      )
    ORDER BY xi.op_date DESC, xi.id DESC;
END;
$$ LANGUAGE plpgsql;

-- 24. Дерево классификатора ХО
CREATE OR REPLACE FUNCTION get_xo_class_tree(p_parent_id INTEGER DEFAULT NULL)
RETURNS TABLE (
    id          INTEGER,
    name        VARCHAR(255),
    description TEXT,
    parent_id   INTEGER,
    sort_order  INTEGER,
    depth       INTEGER,
    instance_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE tree AS (
        SELECT xc.id, xc.name, xc.description, xc.parent_id, xc.sort_order, 0 AS depth
        FROM xo_class xc
        WHERE (p_parent_id IS NULL AND xc.parent_id IS NULL)
           OR (p_parent_id IS NOT NULL AND xc.parent_id = p_parent_id)
        UNION ALL
        SELECT xc.id, xc.name, xc.description, xc.parent_id, xc.sort_order, t.depth + 1
        FROM xo_class xc JOIN tree t ON xc.parent_id = t.id
    )
    SELECT t.id, t.name, t.description, t.parent_id, t.sort_order, t.depth,
           COUNT(xi.id) AS instance_count
    FROM tree t
    LEFT JOIN xo_instance xi ON xi.xo_class_id = t.id
    GROUP BY t.id, t.name, t.description, t.parent_id, t.sort_order, t.depth
    ORDER BY t.depth, t.sort_order, t.name;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- ТЕСТОВЫЕ ДАННЫЕ: ШАБЛОНЫ И ЭКЗЕМПЛЯРЫ ХО
-- =============================================

DO $$ DECLARE
    -- классы
    cls_root   INTEGER;
    cls_shp    INTEGER;
    cls_recv   INTEGER;
    cls_move   INTEGER;
    cls_inv    INTEGER;
    -- параметры
    p_sum_id   INTEGER;
    p_doc_id   INTEGER;
    p_comment  INTEGER;
    p_fact_id  INTEGER;
    p_book_id  INTEGER;
    -- роли
    r_shp_sup  INTEGER;
    r_shp_cust INTEGER;
    r_recv_sup INTEGER;
    r_recv_wh  INTEGER;
    r_move_src INTEGER;
    r_move_dst INTEGER;
    r_inv_mol  INTEGER;
    r_inv_wh   INTEGER;
    -- экземпляры
    xo1 INTEGER; xo2 INTEGER; xo3 INTEGER; xo4 INTEGER; xo5 INTEGER;
BEGIN

    -- ===== ПАРАМЕТРЫ (общие для ХО) =====
    INSERT INTO param_definition(name, description, param_type, unit, min_value)
    VALUES ('Сумма документа', 'Итоговая денежная сумма ХО', 'numeric', 'руб.', 0)
    RETURNING id INTO p_sum_id;

    INSERT INTO param_definition(name, description, param_type)
    VALUES ('Примечание к ХО', 'Произвольный текстовый комментарий', 'numeric')
    RETURNING id INTO p_comment;
    -- text_value используем через param_type numeric (храним в text_value)

    INSERT INTO param_definition(name, description, param_type, min_value)
    VALUES ('Количество позиций', 'Число строк в табличной части', 'numeric', 1)
    RETURNING id INTO p_doc_id;

    INSERT INTO param_definition(name, description, param_type, unit, min_value)
    VALUES ('Фактический остаток', 'Реальное количество ТМЦ при инвентаризации', 'numeric', 'шт.', 0)
    RETURNING id INTO p_fact_id;

    INSERT INTO param_definition(name, description, param_type, unit, min_value)
    VALUES ('Учётный остаток', 'Остаток ТМЦ по данным учёта', 'numeric', 'шт.', 0)
    RETURNING id INTO p_book_id;

    -- ===== КЛАССИФИКАТОР КЛАССОВ ХО =====
    cls_root := add_xo_class('Хозяйственные операции', 'Корневой класс ХО', NULL, 0);
    cls_shp  := add_xo_class('Отгрузка товара', 'Отпуск товара покупателю (ТОРГ-12)', cls_root, 1);
    cls_recv := add_xo_class('Поступление товара', 'Приём товара от поставщика', cls_root, 2);
    cls_move := add_xo_class('Внутреннее перемещение', 'Перемещение между складами', cls_root, 3);
    cls_inv  := add_xo_class('Инвентаризация', 'Проверка фактического наличия ТМЦ', cls_root, 4);

    -- ===== ПАРАМЕТРЫ КЛАССОВ ХО =====
    -- Корневому классу: общий наследуемый параметр «Сумма»
    PERFORM assign_param_to_xo_class(cls_root, p_sum_id, TRUE, 1);

    -- Отгрузке: кол-во позиций (не наследуется)
    PERFORM assign_param_to_xo_class(cls_shp, p_doc_id, FALSE, 2);

    -- Поступлению: кол-во позиций
    PERFORM assign_param_to_xo_class(cls_recv, p_doc_id, FALSE, 2);

    -- Инвентаризации: фактический и учётный остаток
    PERFORM assign_param_to_xo_class(cls_inv, p_fact_id, FALSE, 2);
    PERFORM assign_param_to_xo_class(cls_inv, p_book_id, FALSE, 3);

    -- ===== РОЛИ =====
    r_shp_sup  := add_xo_role_def(cls_shp, 'Поставщик',   'Сторона, отпускающая товар', TRUE, 'organization');
    r_shp_cust := add_xo_role_def(cls_shp, 'Покупатель',  'Сторона, получающая товар',  TRUE, 'organization');

    r_recv_sup := add_xo_role_def(cls_recv, 'Поставщик',  'Поставщик товара',   TRUE,  'organization');
    r_recv_wh  := add_xo_role_def(cls_recv, 'Склад',      'Склад-получатель',   TRUE,  'warehouse');

    r_move_src := add_xo_role_def(cls_move, 'Склад-источник',    'Откуда перемещают',  TRUE, 'warehouse');
    r_move_dst := add_xo_role_def(cls_move, 'Склад-назначение',  'Куда перемещают',    TRUE, 'warehouse');

    r_inv_mol  := add_xo_role_def(cls_inv,  'МОЛ',               'Материально ответственное лицо', TRUE, 'person');
    r_inv_wh   := add_xo_role_def(cls_inv,  'Склад',             'Склад инвентаризации',           TRUE, 'warehouse');

    -- ===== ЭКЗЕМПЛЯРЫ ХО =====

    -- ХО 1: Отгрузка ТН-2024-0001
    xo1 := create_xo_instance(cls_shp, 'ТН-2024-0001', '2024-03-15', 'Отгрузка весеннего ассортимента', 'operator1');
    PERFORM set_xo_param_value(xo1, p_sum_id, 4235.50);
    PERFORM set_xo_param_value(xo1, p_doc_id, 3);
    PERFORM assign_xo_role(xo1, r_shp_sup,  'ООО СадПоставка', 1, 'organization');
    PERFORM assign_xo_role(xo1, r_shp_cust, 'ИП Иванов А.В.',  2, 'organization');
    PERFORM add_xo_line(xo1,
        (SELECT id FROM product WHERE name='Огурец засолочный' LIMIT 1), 10, 45.50, 'г');
    PERFORM add_xo_line(xo1,
        (SELECT id FROM product WHERE name='Томат сибирский' LIMIT 1),    5, 38.00, 'г');
    PERFORM add_xo_line(xo1,
        (SELECT id FROM product WHERE name='Секатор садовый' LIMIT 1),    2, 1250.00, 'шт.');
    PERFORM post_xo(xo1);

    -- ХО 2: Отгрузка ТН-2024-0002
    xo2 := create_xo_instance(cls_shp, 'ТН-2024-0002', '2024-03-22', NULL, 'operator1');
    PERFORM set_xo_param_value(xo2, p_sum_id, 8900.00);
    PERFORM set_xo_param_value(xo2, p_doc_id, 2);
    PERFORM assign_xo_role(xo2, r_shp_sup,  'ООО СадПоставка',  1, 'organization');
    PERFORM assign_xo_role(xo2, r_shp_cust, 'ООО Зелёный мир',  3, 'organization');
    PERFORM add_xo_line(xo2,
        (SELECT id FROM product WHERE name='Вилка садовая' LIMIT 1),      5, 890.00, 'шт.');
    PERFORM add_xo_line(xo2,
        (SELECT id FROM product WHERE name='Ножницы садовые' LIMIT 1),    4, 670.00, 'шт.');
    PERFORM post_xo(xo2);

    -- ХО 3: Поступление ПН-2024-0101
    xo3 := create_xo_instance(cls_recv, 'ПН-2024-0101', '2024-03-10', 'Весенний завоз семян', 'operator2');
    PERFORM set_xo_param_value(xo3, p_sum_id, 12500.00);
    PERFORM set_xo_param_value(xo3, p_doc_id, 2);
    PERFORM assign_xo_role(xo3, r_recv_sup, 'АО АгроСемена',  4, 'organization');
    PERFORM assign_xo_role(xo3, r_recv_wh,  'Главный склад',  1, 'warehouse');
    PERFORM add_xo_line(xo3,
        (SELECT id FROM product WHERE name='Огурец засолочный' LIMIT 1), 100, 35.00, 'г');
    PERFORM add_xo_line(xo3,
        (SELECT id FROM product WHERE name='Томат сибирский' LIMIT 1),    50, 30.00, 'г');
    PERFORM post_xo(xo3);

    -- ХО 4: Внутреннее перемещение ВП-2024-0003 (черновик)
    xo4 := create_xo_instance(cls_move, 'ВП-2024-0003', '2024-04-01', 'Перемещение инвентаря', 'operator1');
    PERFORM set_xo_param_value(xo4, p_sum_id, 0);
    PERFORM assign_xo_role(xo4, r_move_src, 'Склад №1',  1, 'warehouse');
    PERFORM assign_xo_role(xo4, r_move_dst, 'Склад №2',  2, 'warehouse');
    PERFORM add_xo_line(xo4,
        (SELECT id FROM product WHERE name='Секатор садовый' LIMIT 1), 3, NULL, 'шт.');
    -- Оставляем в черновике

    -- ХО 5: Инвентаризация ИНВ-2024-0001
    xo5 := create_xo_instance(cls_inv, 'ИНВ-2024-0001', '2024-03-31', 'Квартальная инвентаризация', 'admin');
    PERFORM set_xo_param_value(xo5, p_fact_id, 48);
    PERFORM set_xo_param_value(xo5, p_book_id, 50);
    PERFORM assign_xo_role(xo5, r_inv_mol, 'Петрова М.С.',  10, 'person');
    PERFORM assign_xo_role(xo5, r_inv_wh,  'Главный склад',  1, 'warehouse');
    PERFORM post_xo(xo5);

    RAISE NOTICE 'Тестовые данные ХО успешно загружены!';
    RAISE NOTICE 'Классы ХО: root=%, отгрузка=%, поступление=%, перемещение=%, инвентаризация=%',
        cls_root, cls_shp, cls_recv, cls_move, cls_inv;
    RAISE NOTICE 'Экземпляры: ТН-0001=%, ТН-0002=%, ПН-0101=%, ВП-0003=%, ИНВ-0001=%',
        xo1, xo2, xo3, xo4, xo5;
END $$;

COMMIT;