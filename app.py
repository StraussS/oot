import base64
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "oot.db"
UPLOAD_DIR = BASE_DIR / "uploads"
IMAGE_DIR = UPLOAD_DIR / "images"
INVOICE_DIR = UPLOAD_DIR / "invoices"
for d in [UPLOAD_DIR, IMAGE_DIR, INVOICE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

STATUS_ACTIVE = "服役中"
STATUS_RETIRED = "已退役"
STATUS_SOLD = "已卖出"
ITEM_TYPE_ASSET = "资产"
ITEM_TYPE_WISH = "心愿"


@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#111827',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL DEFAULT 0,
            purchase_date TEXT,
            category_id INTEGER,
            target_cost REAL,
            note TEXT,
            image_url TEXT,
            invoice_path TEXT,
            include_in_total INTEGER DEFAULT 1,
            include_in_daily INTEGER DEFAULT 1,
            status TEXT DEFAULT '服役中',
            expiry_date TEXT,
            expiry_reminder INTEGER DEFAULT 0,
            sold_price REAL,
            sold_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS item_tags (
            item_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (item_id, tag_id),
            FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE,
            FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        """
    )
    ensure_column(conn, "items", "invoice_path", "TEXT")
    defaults = ["手机", "电脑", "音频", "相机", "家居", "订阅", "其它"]
    for name in defaults:
        conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (name,))
    conn.commit()


def ensure_column(conn, table, column, coltype):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        conn.commit()


def qdf(conn, query, params=()):
    return pd.read_sql_query(query, conn, params=params)


def fetch_categories(conn):
    return qdf(conn, "SELECT id, name FROM categories ORDER BY id")


def fetch_tags(conn):
    return qdf(conn, "SELECT id, name FROM tags ORDER BY name")


def item_list(conn, item_type=None, status=None, keyword=""):
    sql = """
    SELECT i.*, c.name AS category_name,
           GROUP_CONCAT(t.name, ' / ') AS tag_names
    FROM items i
    LEFT JOIN categories c ON c.id = i.category_id
    LEFT JOIN item_tags it ON it.item_id = i.id
    LEFT JOIN tags t ON t.id = it.tag_id
    WHERE 1=1
    """
    params = []
    if item_type:
        sql += " AND i.item_type = ?"
        params.append(item_type)
    if status:
        sql += " AND i.status = ?"
        params.append(status)
    if keyword.strip():
        sql += " AND (i.name LIKE ? OR IFNULL(i.note,'') LIKE ?)"
        like = f"%{keyword.strip()}%"
        params.extend([like, like])
    sql += " GROUP BY i.id ORDER BY datetime(i.created_at) DESC"
    return qdf(conn, sql, params)


def metric_summary(conn):
    asset_df = qdf(conn, "SELECT * FROM items WHERE item_type='资产'")
    wish_df = qdf(conn, "SELECT * FROM items WHERE item_type='心愿'")
    if asset_df.empty:
        total_assets = daily_cost = 0.0
        active = retired = sold = 0
    else:
        total_assets = asset_df.loc[asset_df["include_in_total"] == 1, "price"].fillna(0).sum()
        active = int((asset_df["status"] == STATUS_ACTIVE).sum())
        retired = int((asset_df["status"] == STATUS_RETIRED).sum())
        sold = int((asset_df["status"] == STATUS_SOLD).sum())
        daily_vals = []
        for _, row in asset_df.loc[asset_df["include_in_daily"] == 1].iterrows():
            if row["purchase_date"]:
                try:
                    days = max((date.today() - datetime.strptime(row["purchase_date"], "%Y-%m-%d").date()).days, 1)
                    daily_vals.append((row["price"] or 0) / days)
                except ValueError:
                    pass
        daily_cost = sum(daily_vals)
    expiring = qdf(conn, "SELECT name, expiry_date, item_type, status FROM items WHERE expiry_date IS NOT NULL ORDER BY expiry_date ASC LIMIT 6")
    return {
        "total_assets": total_assets,
        "daily_cost": daily_cost,
        "active": active,
        "retired": retired,
        "sold": sold,
        "wishlist_total": wish_df["price"].fillna(0).sum() if not wish_df.empty else 0,
        "wishlist_count": len(wish_df),
        "all_count": len(asset_df) + len(wish_df),
        "expiring": expiring,
    }


def save_uploaded_file(uploaded_file, folder: Path):
    if uploaded_file is None:
        return None
    suffix = Path(uploaded_file.name).suffix or ""
    filename = f"{uuid.uuid4().hex}{suffix}"
    target = folder / filename
    target.write_bytes(uploaded_file.getbuffer())
    return str(target)


def remove_local_file(path_str):
    if not path_str:
        return
    try:
        p = Path(path_str)
        if p.exists() and p.is_file() and UPLOAD_DIR in p.parents:
            p.unlink(missing_ok=True)
    except Exception:
        pass


def image_src(path_or_url):
    if not path_or_url:
        return None
    p = Path(str(path_or_url))
    if p.exists() and p.is_file():
        data = p.read_bytes()
        ext = p.suffix.lower().lstrip('.') or 'png'
        img_type = 'jpeg' if ext == 'jpg' else ext
        return f"data:image/{img_type};base64,{base64.b64encode(data).decode()}"
    return str(path_or_url)


def create_item(conn, data, tag_ids):
    cur = conn.execute(
        """
        INSERT INTO items (
            item_type, name, price, purchase_date, category_id, target_cost, note,
            image_url, invoice_path, include_in_total, include_in_daily, status, expiry_date,
            expiry_reminder, sold_price, sold_date, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            data["item_type"], data["name"], data["price"], data["purchase_date"],
            data["category_id"], data["target_cost"], data["note"], data["image_url"], data["invoice_path"],
            int(data["include_in_total"]), int(data["include_in_daily"]), data["status"],
            data["expiry_date"], int(data["expiry_reminder"]), data["sold_price"], data["sold_date"],
        ),
    )
    item_id = cur.lastrowid
    for tag_id in tag_ids:
        conn.execute("INSERT INTO item_tags(item_id, tag_id) VALUES (?, ?)", (item_id, int(tag_id)))
    conn.commit()


def update_item(conn, item_id, data, tag_ids):
    old_row = conn.execute("SELECT image_url, invoice_path FROM items WHERE id=?", (item_id,)).fetchone()
    conn.execute(
        """
        UPDATE items SET
            item_type=?, name=?, price=?, purchase_date=?, category_id=?, target_cost=?, note=?,
            image_url=?, invoice_path=?, include_in_total=?, include_in_daily=?, status=?, expiry_date=?,
            expiry_reminder=?, sold_price=?, sold_date=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            data["item_type"], data["name"], data["price"], data["purchase_date"],
            data["category_id"], data["target_cost"], data["note"], data["image_url"], data["invoice_path"],
            int(data["include_in_total"]), int(data["include_in_daily"]), data["status"],
            data["expiry_date"], int(data["expiry_reminder"]), data["sold_price"], data["sold_date"], item_id,
        ),
    )
    conn.execute("DELETE FROM item_tags WHERE item_id=?", (item_id,))
    for tag_id in tag_ids:
        conn.execute("INSERT INTO item_tags(item_id, tag_id) VALUES (?, ?)", (item_id, int(tag_id)))
    conn.commit()
    if old_row:
        if old_row[0] and old_row[0] != data["image_url"]:
            remove_local_file(old_row[0])
        if old_row[1] and old_row[1] != data["invoice_path"]:
            remove_local_file(old_row[1])


def delete_item(conn, item_id):
    old_row = conn.execute("SELECT image_url, invoice_path FROM items WHERE id=?", (item_id,)).fetchone()
    conn.execute("DELETE FROM item_tags WHERE item_id=?", (item_id,))
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    if old_row:
        remove_local_file(old_row[0])
        remove_local_file(old_row[1])


def add_category(conn, name):
    conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (name.strip(),))
    conn.commit()


def add_tag(conn, name):
    conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name.strip(),))
    conn.commit()


def delete_category(conn, category_id):
    conn.execute("UPDATE items SET category_id=NULL WHERE category_id=?", (category_id,))
    conn.execute("DELETE FROM categories WHERE id=?", (category_id,))
    conn.commit()


def delete_tag(conn, tag_id):
    conn.execute("DELETE FROM item_tags WHERE tag_id=?", (tag_id,))
    conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))
    conn.commit()


def count_items_by_category(conn, category_id):
    df = qdf(conn, "SELECT COUNT(*) AS cnt FROM items WHERE category_id=?", (category_id,))
    return int(df.iloc[0]["cnt"]) if not df.empty else 0


def count_items_by_tag(conn, tag_id):
    df = qdf(conn, "SELECT COUNT(*) AS cnt FROM item_tags WHERE tag_id=?", (tag_id,))
    return int(df.iloc[0]["cnt"]) if not df.empty else 0


def format_money(v):
    return f"¥{float(v or 0):,.2f}"


def fmt_date(s):
    return s or "未填写"


def inject_css():
    st.markdown(
        """
        <style>
        :root {
            --bg-top:#f5f7ff;
            --bg-bottom:#eef2ff;
            --surface:#ffffffee;
            --surface-soft:#f8faff;
            --line:#e3e8ff;
            --text:#0f172a;
            --muted:#64748b;
            --brand-1:#4f46e5;
            --brand-2:#7c3aed;
            --brand-3:#ec4899;
            --state-active:#0891b2;
            --state-retired:#ea580c;
            --state-sold:#7c3aed;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(79,70,229,.12), transparent 24%),
                radial-gradient(circle at top right, rgba(236,72,153,.08), transparent 18%),
                linear-gradient(180deg,var(--bg-top) 0%, var(--bg-bottom) 100%);
            color:var(--text);
        }
        .block-container {
            padding-top:1.15rem;
            padding-bottom:2.4rem;
            max-width:1180px;
        }
        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at top left, rgba(79,70,229,.08), transparent 26%),
                linear-gradient(180deg,#fcfcff 0%, #f4f7ff 100%);
            border-right:1px solid rgba(79,70,229,.08);
        }
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color:#312e81;
        }
        [data-testid="stSidebar"] [data-testid="stForm"] {
            background:rgba(255,255,255,.72);
            border:1px solid #e3e8ff;
            border-radius:18px;
            padding:1rem .85rem .4rem .85rem;
            box-shadow:0 10px 24px rgba(79,70,229,.06);
        }
        [data-testid="stSidebar"] .stSegmentedControl {
            margin-bottom:.2rem;
        }
        h1,h2,h3 {color:var(--text); letter-spacing:-.02em;}
        .hero {
            background:linear-gradient(135deg,#111827 0%, #4338ca 46%, #7c3aed 72%, #ec4899 100%);
            color:white;
            border-radius:26px;
            padding:1.4rem 1.45rem;
            box-shadow:0 22px 46px rgba(79,70,229,.18);
            position:relative;
            overflow:hidden;
        }
        .hero::after {
            content:"";
            position:absolute;
            top:-70px; right:-60px;
            width:210px; height:210px;
            background:radial-gradient(circle, rgba(255,255,255,.18) 0%, rgba(255,255,255,0) 70%);
        }
        .card {
            background:var(--surface);
            backdrop-filter:blur(10px);
            border-radius:20px;
            padding:1rem 1.05rem;
            box-shadow:0 12px 26px rgba(15,23,42,.06);
            border:1px solid rgba(255,255,255,.8);
        }
        .mini {
            background:linear-gradient(180deg,#ffffff 0%, var(--surface-soft) 100%);
            border:1px solid #e6eaf8;
            border-radius:16px;
            padding:1rem;
            min-height:118px;
            box-shadow:0 10px 22px rgba(15,23,42,.05);
        }
        .muted {color:var(--muted); font-size:.92rem;}
        .item-card {
            background:linear-gradient(180deg,#ffffff 0%, #fbfcff 100%);
            border:1px solid #e7eaf7;
            border-radius:20px;
            padding:1rem;
            margin-bottom:1rem;
            box-shadow:0 12px 24px rgba(15,23,42,.05);
            transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease;
        }
        .item-card:hover {
            transform:translateY(-1px);
            border-color:#d9ddff;
            box-shadow:0 16px 30px rgba(79,70,229,.08);
        }
        .pill {
            display:inline-block;
            padding:.24rem .62rem;
            border-radius:999px;
            background:linear-gradient(135deg,#eef2ff 0%, #f5ecff 100%);
            color:var(--brand-1);
            border:1px solid #e0e7ff;
            font-size:.79rem;
            margin-right:.35rem;
            margin-top:.3rem;
        }
        .section-title{font-size:1.08rem;font-weight:700;margin:.35rem 0 .8rem 0;}
        .small-kpi{font-size:1.65rem;font-weight:800;margin:.28rem 0;}
        .thumb-wrap{
            width:74px;height:74px;border-radius:18px;overflow:hidden;
            background:linear-gradient(135deg,#eef2ff 0%, #fae8ff 100%);
            display:flex;align-items:center;justify-content:center;
            border:1px solid #e5e7eb;
        }
        .invoice-box{
            padding:.75rem .9rem;
            border:1px dashed #c7d2fe;
            border-radius:14px;
            background:linear-gradient(180deg,#fafbff 0%, #f5f3ff 100%);
        }
        [data-testid="stSegmentedControl"] {
            background:linear-gradient(180deg,#ffffff 0%, #f8faff 100%);
            padding:.38rem;
            border-radius:16px;
            border:1px solid var(--line);
            box-shadow:0 8px 22px rgba(79,70,229,.06);
        }
        [data-testid="stSegmentedControl"] button {
            border-radius:12px !important;
            font-weight:700 !important;
            min-height:42px;
            color:#334155 !important;
        }
        [data-testid="stSegmentedControl"] button[aria-pressed="true"] {
            background:linear-gradient(135deg,var(--brand-1) 0%, var(--brand-2) 100%) !important;
            color:white !important;
            box-shadow:0 8px 18px rgba(79,70,229,.2);
        }
        .stButton>button, .stDownloadButton>button {
            border-radius:14px !important;
            border:1px solid #dbe4ff !important;
            background:linear-gradient(180deg,#ffffff 0%, #f7f9ff 100%) !important;
            color:#1e293b !important;
            font-weight:600 !important;
            box-shadow:0 4px 12px rgba(15,23,42,.04);
        }
        .stButton>button:hover, .stDownloadButton>button:hover {
            border-color:#c7d2fe !important;
            color:#312e81 !important;
            box-shadow:0 8px 18px rgba(79,70,229,.10);
        }
        .stTextInput input, .stNumberInput input, .stTextArea textarea {
            border-radius:14px !important;
            border:1px solid #dbe4ff !important;
            background:#ffffff !important;
            box-shadow:none !important;
            outline:none !important;
        }
        .stTextInput > div > div,
        .stNumberInput > div > div,
        .stTextArea > div > div {
            border-radius:14px !important;
        }
        .stTextInput > div > div:focus-within,
        .stNumberInput > div > div:focus-within,
        .stTextArea > div > div:focus-within {
            border-radius:14px !important;
            box-shadow:0 0 0 3px rgba(99,102,241,.12) !important;
        }
        .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
            border-color:#a5b4fc !important;
            box-shadow:none !important;
            border-radius:14px !important;
            outline:none !important;
        }
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div {
            border-radius:14px !important;
            border-color:#dbe4ff !important;
            min-height:44px;
            box-shadow:none !important;
        }
        .stSelectbox [data-baseweb="select"] > div:focus-within,
        .stMultiSelect [data-baseweb="select"] > div:focus-within {
            border-color:#a5b4fc !important;
            box-shadow:0 0 0 3px rgba(99,102,241,.12) !important;
            border-radius:14px !important;
        }
        div[data-testid="stFileUploader"] section {
            border-radius:16px !important;
            border:1px dashed #c7d2fe !important;
            background:linear-gradient(180deg,#fafbff 0%, #f5f7ff 100%) !important;
        }
        [data-testid="stRadio"] label {
            border:1px solid #e7eaf7;
            background:linear-gradient(180deg,#ffffff 0%, #fbfcff 100%);
            border-radius:12px;
            padding:.55rem .7rem;
            margin-bottom:.45rem;
            box-shadow:none;
            transition:all .15s ease;
        }
        [data-testid="stRadio"] label:has(input:checked) {
            border:1px solid #8b5cf6 !important;
            background:linear-gradient(135deg,#f5f3ff 0%, #eef2ff 100%) !important;
            box-shadow:0 0 0 2px rgba(139,92,246,.10);
        }
        [data-testid="stRadio"] label:has(input:checked) > div {
            color:#4c1d95 !important;
            font-weight:700;
        }
        [data-testid="stExpander"] details {
            border:1px solid #e8ebf8 !important;
            border-radius:12px !important;
            background:#ffffffb8 !important;
        }
        [data-testid="stDataFrame"] {
            border-radius:16px;
            overflow:hidden;
            border:1px solid #e7eaf7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def top_summary(conn):
    s = metric_summary(conn)
    cols = st.columns([1.5, 1, 1, 1])
    with cols[0]:
        st.markdown(
            f"""
            <div class='hero'>
              <div style='font-size:.92rem;opacity:.9'>资产总览</div>
              <div class='small-kpi' style='margin-top:.45rem'>{format_money(s['total_assets'])}</div>
              <div style='opacity:.9'>日均成本：{format_money(s['daily_cost'])}</div>
              <div style='margin-top:.9rem;display:flex;gap:1rem;opacity:.95'>
                <div>总条目 {s['all_count']}</div>
                <div>心愿 {s['wishlist_count']}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    metrics = [
        ("服役中", s["active"], "linear-gradient(135deg,#ecfeff 0%, #dbeafe 100%)", "#0891b2"),
        ("已退役", s["retired"], "linear-gradient(135deg,#fff7ed 0%, #ffedd5 100%)", "#ea580c"),
        ("已卖出", s["sold"], "linear-gradient(135deg,#f5f3ff 0%, #ede9fe 100%)", "#7c3aed"),
    ]
    for col, (label, val, bg, accent) in zip(cols[1:], metrics):
        with col:
            st.markdown(
                f"""
                <div class='mini' style='background:{bg};border-color:rgba(255,255,255,.75)'>
                  <div class='muted' style='color:{accent};font-weight:700'>{label}</div>
                  <div class='small-kpi' style='color:#0f172a'>{val}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_item_detail(row):
    with st.expander(f"查看详情：{row['name']}"):
        c1, c2 = st.columns([1, 1.2])
        with c1:
            if row["image_url"]:
                st.image(row["image_url"], use_container_width=True)
            else:
                st.info("暂无图片")
            if row.get("invoice_path"):
                st.markdown("<div class='invoice-box'>已上传发票</div>", unsafe_allow_html=True)
                invoice_path = Path(row["invoice_path"])
                if invoice_path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} and invoice_path.exists():
                    st.image(str(invoice_path), use_container_width=True)
                with open(row["invoice_path"], "rb") as f:
                    st.download_button("下载发票", data=f.read(), file_name=Path(row["invoice_path"]).name, use_container_width=True)
        with c2:
            st.write(f"**类型：** {row['item_type']}")
            st.write(f"**状态：** {row['status']}")
            st.write(f"**类别：** {row['category_name'] or '未分类'}")
            st.write(f"**价格：** {format_money(row['price'])}")
            st.write(f"**目标成本：** {format_money(row['target_cost'])}")
            st.write(f"**购买日期：** {fmt_date(row['purchase_date'])}")
            st.write(f"**到期日期：** {fmt_date(row['expiry_date'])}")
            st.write(f"**卖出价格：** {format_money(row['sold_price'])}")
            st.write(f"**卖出日期：** {fmt_date(row['sold_date'])}")
            if row["note"]:
                st.write(f"**备注：** {row['note']}")


def render_edit_form(conn, row, categories, tags):
    with st.expander(f"编辑：{row['name']}"):
        tag_id_map = {r['name']: int(r['id']) for _, r in tags.iterrows()} if not tags.empty else {}
        default_tags = [x for x in (row['tag_names'] or '').split(' / ') if x in tag_id_map]
        cat_names = ["未分类"] + categories["name"].tolist()
        default_cat = row['category_name'] if row['category_name'] in cat_names else "未分类"
        with st.form(f"edit_{int(row['id'])}"):
            c1, c2 = st.columns(2)
            with c1:
                item_type = st.selectbox("类型", [ITEM_TYPE_ASSET, ITEM_TYPE_WISH], index=0 if row['item_type'] == ITEM_TYPE_ASSET else 1)
                name = st.text_input("物品名称", value=row['name'])
                image_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg", "webp"], key=f"img_{int(row['id'])}")
                if row['image_url']:
                    st.caption("当前图片已存在，可重新上传替换")
                invoice_file = st.file_uploader("上传发票", type=["png", "jpg", "jpeg", "webp", "pdf"], key=f"invoice_{int(row['id'])}")
                price = st.number_input("价格", min_value=0.0, value=float(row['price'] or 0), step=100.0)
                purchase_date = st.text_input("购买日期", value=row['purchase_date'] or "")
                category_name = st.selectbox("类别", cat_names, index=cat_names.index(default_cat))
                selected_tags = st.multiselect("标签", list(tag_id_map.keys()), default=default_tags)
            with c2:
                target_cost = st.number_input("目标成本", min_value=0.0, value=float(row['target_cost'] or 0), step=100.0)
                note = st.text_area("备注", value=row['note'] or "", max_chars=200)
                include_total = st.checkbox("计入总资产", value=bool(row['include_in_total']))
                include_daily = st.checkbox("计入日均", value=bool(row['include_in_daily']))
                status = st.selectbox("状态", [STATUS_ACTIVE, STATUS_RETIRED, STATUS_SOLD], index=[STATUS_ACTIVE, STATUS_RETIRED, STATUS_SOLD].index(row['status']))
                expiry_date = st.text_input("到期日期", value=row['expiry_date'] or "")
                expiry_reminder = st.checkbox("开启到期提醒", value=bool(row['expiry_reminder']))
                sold_price = st.number_input("卖出价格", min_value=0.0, value=float(row['sold_price'] or 0), step=100.0)
                sold_date = st.text_input("卖出日期", value=row['sold_date'] or "")
            save = st.form_submit_button("保存修改")
        if save:
            category_id = None
            if category_name != "未分类":
                category_id = int(categories.loc[categories['name'] == category_name, 'id'].iloc[0])
            image_path = save_uploaded_file(image_file, IMAGE_DIR) if image_file else row['image_url']
            invoice_path = save_uploaded_file(invoice_file, INVOICE_DIR) if invoice_file else row.get('invoice_path')
            update_item(conn, int(row['id']), {
                'item_type': item_type,
                'name': name,
                'price': price,
                'purchase_date': purchase_date or None,
                'category_id': category_id,
                'target_cost': target_cost,
                'note': note,
                'image_url': image_path,
                'invoice_path': invoice_path,
                'include_in_total': include_total,
                'include_in_daily': include_daily,
                'status': status,
                'expiry_date': expiry_date or None,
                'expiry_reminder': expiry_reminder,
                'sold_price': sold_price,
                'sold_date': sold_date or None,
            }, [tag_id_map[t] for t in selected_tags])
            st.success("已更新")
            st.rerun()


def render_item_cards(df, conn):
    categories = fetch_categories(conn)
    tags = fetch_tags(conn)
    if df.empty:
        st.markdown("<div class='card' style='text-align:center;padding:2.4rem'>空空如也<br><span class='muted'>左侧可以直接新增资产 / 心愿</span></div>", unsafe_allow_html=True)
        return
    for _, row in df.iterrows():
        tags_html = "".join([f"<span class='pill'>{t}</span>" for t in (row['tag_names'] or '').split(' / ') if t])
        src = image_src(row['image_url'])
        image_html = f"<div class='thumb-wrap'><img src='{src}' style='width:100%;height:100%;object-fit:cover'></div>" if src else "<div class='thumb-wrap' style='font-size:1.5rem'>📦</div>"
        invoice_badge = "<span class='pill'>有发票</span>" if row.get('invoice_path') else ""
        st.markdown(
            f"""
            <div class='item-card'>
              <div style='display:flex;gap:1rem'>
                {image_html}
                <div style='flex:1'>
                  <div style='display:flex;justify-content:space-between;gap:1rem;align-items:flex-start'>
                    <div>
                      <div style='font-size:1.06rem;font-weight:800'>{row['name']}</div>
                      <div class='muted'>{row['category_name'] or '未分类'} · {row['status']} · {row['item_type']}</div>
                    </div>
                    <div style='text-align:right'>
                      <div style='font-weight:800'>{format_money(row['price'])}</div>
                      <div class='muted'>目标 {format_money(row['target_cost'])}</div>
                    </div>
                  </div>
                  <div class='muted' style='margin-top:.45rem'>购买日期：{fmt_date(row['purchase_date'])}　到期：{fmt_date(row['expiry_date'])}</div>
                  <div style='margin-top:.45rem'>{tags_html}{invoice_badge}</div>
                  <div class='muted' style='margin-top:.45rem'>{row['note'] or ''}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            render_item_detail(row)
        with c2:
            render_edit_form(conn, row, categories, tags)
        if st.button(f"删除 #{int(row['id'])} {row['name']}", key=f"del_{int(row['id'])}"):
            delete_item(conn, int(row['id']))
            st.rerun()


def page_assets(conn):
    top_summary(conn)
    st.write("")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        picked = st.segmented_control("资产状态", ["全部", STATUS_ACTIVE, STATUS_RETIRED, STATUS_SOLD], default="全部")
    with c2:
        keyword = st.text_input("搜索资产", placeholder="名称 / 备注")
    render_item_cards(item_list(conn, ITEM_TYPE_ASSET, None if picked == "全部" else picked, keyword), conn)


def page_wishlist(conn):
    s = metric_summary(conn)
    st.markdown(f"<div class='card'><div class='muted'>心愿总值</div><div class='small-kpi'>{format_money(s['wishlist_total'])}</div><div class='muted'>心愿数量 {s['wishlist_count']} 个</div></div>", unsafe_allow_html=True)
    keyword = st.text_input("搜索心愿", placeholder="名称 / 备注", key="wish_kw")
    render_item_cards(item_list(conn, ITEM_TYPE_WISH, None, keyword), conn)


def page_stats(conn):
    st.markdown("<div class='card'><div class='section-title'>数据统计</div><div class='muted'>从心愿到持有、退役、卖出，完整看见你的物品变化。</div></div>", unsafe_allow_html=True)
    df = qdf(conn, "SELECT item_type, status, price, target_cost, include_in_total, include_in_daily FROM items")
    if df.empty:
        st.info("还没有数据，先新增几条资产或心愿。")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("按类型金额")
        st.bar_chart(df.groupby("item_type")["price"].sum())
        st.subheader("状态分布")
        st.bar_chart(df.groupby("status")["price"].sum())
    with c2:
        st.subheader("目标成本对比")
        compare = pd.DataFrame({"实际价格": [df["price"].fillna(0).sum()], "目标成本": [df["target_cost"].fillna(0).sum()]})
        st.bar_chart(compare)
        st.subheader("统计口径")
        metric1, metric2 = st.columns(2)
        metric1.metric("计入总资产", int((df["include_in_total"] == 1).sum()))
        metric2.metric("计入日均", int((df["include_in_daily"] == 1).sum()))
    st.subheader("即将到期")
    exp = metric_summary(conn)["expiring"]
    if exp.empty:
        st.caption("暂无到期项目")
    else:
        st.dataframe(exp, use_container_width=True, hide_index=True)


def page_settings(conn):
    st.markdown("<div class='card'><div class='section-title'>设置与数据管理</div><div class='muted'>管理分类、标签与数据，让每件物品都井井有条。</div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("分类管理")
        cats = fetch_categories(conn)
        t1, t2 = st.columns([2, 1])
        with t1:
            name = st.text_input("分类名称", placeholder="输入分类名称", label_visibility="collapsed")
        with t2:
            add_clicked = st.button("添加分类", use_container_width=True)
        if add_clicked and name.strip():
            add_category(conn, name)
            st.rerun()
        if cats.empty:
            st.caption("暂无分类")
        else:
            cat_names = cats["name"].tolist()
            selected_cat = st.radio("分类列表", cat_names, label_visibility="collapsed")
            selected_cat_id = int(cats.loc[cats["name"] == selected_cat, "id"].iloc[0])
            used = count_items_by_category(conn, selected_cat_id)
            d1, d2 = st.columns([2, 1])
            with d1:
                st.caption(f"已选中：{selected_cat} · 关联物品 {used} 条")
            with d2:
                delete_clicked = st.button("删除分类", use_container_width=True, disabled=not bool(selected_cat), key="delete_category_trigger")
            if delete_clicked:
                st.session_state["confirm_delete_category_id"] = selected_cat_id
                st.session_state["confirm_delete_category_name"] = selected_cat
                st.session_state["confirm_delete_category_count"] = used
            if st.session_state.get("confirm_delete_category_id"):
                st.warning(f"确认删除分类「{st.session_state.get('confirm_delete_category_name')}」？当前关联物品 {st.session_state.get('confirm_delete_category_count')} 条，删除后这些物品会变成未分类。")
                cta1, cta2 = st.columns(2)
                with cta1:
                    if st.button("确认删除分类", use_container_width=True, key="confirm_delete_category"):
                        delete_category(conn, int(st.session_state["confirm_delete_category_id"]))
                        st.session_state["confirm_delete_category_id"] = None
                        st.session_state["confirm_delete_category_name"] = None
                        st.session_state["confirm_delete_category_count"] = None
                        st.rerun()
                with cta2:
                    if st.button("取消", use_container_width=True, key="cancel_delete_category"):
                        st.session_state["confirm_delete_category_id"] = None
                        st.session_state["confirm_delete_category_name"] = None
                        st.session_state["confirm_delete_category_count"] = None
                        st.rerun()
    with c2:
        st.subheader("标签管理")
        tags = fetch_tags(conn)
        t1, t2 = st.columns([2, 1])
        with t1:
            tag = st.text_input("标签名称", placeholder="输入标签名称", label_visibility="collapsed")
        with t2:
            add_tag_clicked = st.button("添加标签", use_container_width=True)
        if add_tag_clicked and tag.strip():
            add_tag(conn, tag)
            st.rerun()
        if tags.empty:
            st.caption("暂无标签")
        else:
            tag_names = tags["name"].tolist()
            selected_tag = st.radio("标签列表", tag_names, label_visibility="collapsed")
            selected_tag_id = int(tags.loc[tags["name"] == selected_tag, "id"].iloc[0])
            used = count_items_by_tag(conn, selected_tag_id)
            d1, d2 = st.columns([2, 1])
            with d1:
                st.caption(f"已选中：{selected_tag} · 关联记录 {used} 条")
            with d2:
                delete_tag_clicked = st.button("删除标签", use_container_width=True, disabled=not bool(selected_tag), key="delete_tag_trigger")
            if delete_tag_clicked:
                st.session_state["confirm_delete_tag_id"] = selected_tag_id
                st.session_state["confirm_delete_tag_name"] = selected_tag
                st.session_state["confirm_delete_tag_count"] = used
            if st.session_state.get("confirm_delete_tag_id"):
                st.warning(f"确认删除标签「{st.session_state.get('confirm_delete_tag_name')}」？当前有 {st.session_state.get('confirm_delete_tag_count')} 条关联记录会被移除。")
                cta1, cta2 = st.columns(2)
                with cta1:
                    if st.button("确认删除标签", use_container_width=True, key="confirm_delete_tag"):
                        delete_tag(conn, int(st.session_state["confirm_delete_tag_id"]))
                        st.session_state["confirm_delete_tag_id"] = None
                        st.session_state["confirm_delete_tag_name"] = None
                        st.session_state["confirm_delete_tag_count"] = None
                        st.rerun()
                with cta2:
                    if st.button("取消", use_container_width=True, key="cancel_delete_tag"):
                        st.session_state["confirm_delete_tag_id"] = None
                        st.session_state["confirm_delete_tag_name"] = None
                        st.session_state["confirm_delete_tag_count"] = None
                        st.rerun()
    st.write("")
    st.subheader("数据导出")
    export_df = item_list(conn)
    st.download_button("导出全部数据 CSV", export_df.to_csv(index=False).encode("utf-8-sig"), file_name="oot_export.csv", mime="text/csv", use_container_width=True)


def create_form(conn):
    st.sidebar.markdown("## 新增物品")
    st.sidebar.caption("快速记录资产、心愿与凭证")
    item_type = st.sidebar.segmented_control("类型", [ITEM_TYPE_ASSET, ITEM_TYPE_WISH], default=ITEM_TYPE_ASSET)
    categories = fetch_categories(conn)
    tags = fetch_tags(conn)
    with st.sidebar.form("create_item"):
        name = st.text_input("物品名称")
        image_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg", "webp"], key="create_image")
        price = st.number_input("价格", min_value=0.0, step=100.0)
        note = st.text_area("备注", max_chars=200)

        if item_type == ITEM_TYPE_ASSET:
            invoice_file = st.file_uploader("上传发票", type=["png", "jpg", "jpeg", "webp", "pdf"], key="create_invoice")
            purchase_date = st.text_input("购买日期", placeholder="YYYY-MM-DD")
            category_name = st.selectbox("类别", ["未分类"] + categories["name"].tolist())
            selected_tags = st.multiselect("标签", tags["name"].tolist())
            target_cost = st.number_input("目标成本", min_value=0.0, step=100.0)
            include_total = st.checkbox("计入总资产", value=True)
            include_daily = st.checkbox("计入日均", value=True)
            status = st.selectbox("状态", [STATUS_ACTIVE, STATUS_RETIRED, STATUS_SOLD])
            expiry_date = st.text_input("到期日期", placeholder="YYYY-MM-DD")
            expiry_reminder = st.checkbox("开启到期提醒")
            sold_price = st.number_input("卖出价格", min_value=0.0, step=100.0)
            sold_date = st.text_input("卖出日期", placeholder="YYYY-MM-DD")
        else:
            invoice_file = None
            purchase_date = None
            category_name = "未分类"
            selected_tags = []
            target_cost = 0.0
            include_total = False
            include_daily = False
            status = STATUS_ACTIVE
            expiry_date = None
            expiry_reminder = False
            sold_price = 0.0
            sold_date = None

        submitted = st.form_submit_button("保存")
    if submitted and name.strip():
        category_id = None
        if category_name != "未分类":
            category_id = int(categories.loc[categories["name"] == category_name, "id"].iloc[0])
        tag_ids = [int(tags.loc[tags["name"] == t, "id"].iloc[0]) for t in selected_tags]
        image_path = save_uploaded_file(image_file, IMAGE_DIR) if image_file else None
        invoice_path = save_uploaded_file(invoice_file, INVOICE_DIR) if invoice_file else None
        create_item(conn, {
            "item_type": item_type,
            "name": name,
            "price": price,
            "purchase_date": purchase_date or None,
            "category_id": category_id,
            "target_cost": target_cost,
            "note": note,
            "image_url": image_path,
            "invoice_path": invoice_path,
            "include_in_total": include_total,
            "include_in_daily": include_daily,
            "status": status,
            "expiry_date": expiry_date or None,
            "expiry_reminder": expiry_reminder,
            "sold_price": sold_price,
            "sold_date": sold_date or None,
        }, tag_ids)
        st.sidebar.success("已保存")
        st.rerun()


def main():
    st.set_page_config(page_title="OOT", page_icon="📦", layout="wide")
    inject_css()
    conn = get_conn()
    st.session_state.setdefault("confirm_delete_category_id", None)
    st.session_state.setdefault("confirm_delete_category_name", None)
    st.session_state.setdefault("confirm_delete_category_count", None)
    st.session_state.setdefault("confirm_delete_tag_id", None)
    st.session_state.setdefault("confirm_delete_tag_name", None)
    st.session_state.setdefault("confirm_delete_tag_count", None)
    create_form(conn)
    st.markdown("""<div style='padding-top:1.7rem;margin-bottom:.9rem'><div style='font-size:2.5rem;font-weight:900;letter-spacing:-.02em;line-height:1.24;color:#4f46e5;margin:0 0 .24rem 0'>OOT</div><div class='muted'>Order of Things · 管理你的心愿、资产与物品生命周期。</div></div>""", unsafe_allow_html=True)
    page = st.segmented_control("导航", ["首页", "心愿", "统计", "设置"], default="首页")
    if page == "首页":
        page_assets(conn)
    elif page == "心愿":
        page_wishlist(conn)
    elif page == "统计":
        page_stats(conn)
    else:
        page_settings(conn)


if __name__ == "__main__":
    main()
