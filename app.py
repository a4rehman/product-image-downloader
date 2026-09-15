import io
import os
import re
import sys
import time
import zipfile
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import streamlit as st

# ============================================================
# PAGE CONFIG & CUSTOM STYLING
# ============================================================

st.set_page_config(
    page_title="Product Image & Info Downloader",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(120deg, #4f46e5 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #64748b;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #4f46e5 0%, #06b6d4 100%);
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-success { background-color: #059669; color: white; }
    .badge-failed { background-color: #dc2626; color: white; }
    .badge-info { background-color: #2563eb; color: white; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Supported image extensions
VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".heic",
    ".heif",
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_filename(text, max_length=100):
    """Make a safe Windows/Linux folder/file name."""
    if pd.isna(text) or text is None:
        return "UNKNOWN"
    text = str(text).strip()
    text = re.sub(r'[<>:"/\\|?*]', "_", text)
    text = re.sub(r"[\x00-\x1f]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(". ")
    if not text:
        text = "UNKNOWN"
    return text[:max_length]


def clean_value(value, default="Not specified"):
    """Convert empty/NaN values into readable text."""
    if pd.isna(value) or value is None:
        return default
    val_str = str(value).strip()
    if not val_str or val_str.lower() in {"nan", "none", "null", "nat"}:
        return default
    return val_str


def get_image_extension(url, content_type=None):
    """Determine image extension from URL or Content-Type header."""
    try:
        path = urlparse(url).path
        ext = Path(unquote(path)).suffix.lower()
        if ext in VALID_EXTENSIONS:
            return ext
    except Exception:
        pass

    if content_type:
        content_type = content_type.lower()
        mapping = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/heic": ".heic",
            "image/heif": ".heif",
        }
        for mime, extension in mapping.items():
            if mime in content_type:
                return extension

    return ".jpg"


def split_image_urls(value, delimiter="|"):
    """Extract valid image URLs from string or list."""
    if pd.isna(value) or value is None:
        return []
    val_str = str(value).strip()
    if not val_str:
        return []

    if delimiter == "Auto":
        # Check for common delimiters
        if "|" in val_str:
            tokens = val_str.split("|")
        elif "\n" in val_str:
            tokens = val_str.split("\n")
        elif "," in val_str:
            tokens = val_str.split(",")
        elif ";" in val_str:
            tokens = val_str.split(";")
        else:
            tokens = val_str.split()
    elif delimiter == "\\n (New Line)":
        tokens = val_str.split("\n")
    else:
        tokens = val_str.split(delimiter)

    urls = []
    for token in tokens:
        token = token.strip()
        if token and token.startswith(("http://", "https://")):
            urls.append(token)
    return urls


def download_single_image(url, destination_base_path, timeout=30, retries=3):
    """Download image with retry support and return status + filepath or error."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                stream=True,
            )
            response.raise_for_status()

            ext = get_image_extension(url, response.headers.get("Content-Type"))
            final_path = destination_base_path.with_suffix(ext)

            with open(final_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)

            return True, final_path.name, None

        except Exception as err:
            if attempt < retries:
                time.sleep(1.5)
            else:
                return False, None, str(err)

    return False, None, "Max retries exceeded"


def create_product_info_text(row, col_map, downloaded_images, failed_images):
    """Generate the formatted product_info.txt content."""
    def get_col(field_key):
        mapped_col = col_map.get(field_key)
        if mapped_col and mapped_col in row:
            return clean_value(row[mapped_col])
        return clean_value(row.get(field_key))

    product_name = get_col("name")
    sku = get_col("sku")
    brand = get_col("brand")
    category = get_col("category")
    price = get_col("price")
    compare_price = get_col("compare at price")
    stock = get_col("stock")
    sizes = get_col("sizes")
    colors = get_col("colors")
    fabric = get_col("fabric")
    tags = get_col("tags")
    description = get_col("description")

    lines = [
        "=" * 60,
        "PRODUCT INFORMATION",
        "=" * 60,
        "",
        "Product Name:",
        product_name,
        "",
        "SKU:",
        sku,
        "",
        "Brand:",
        brand,
        "",
        "Category:",
        category,
        "",
        "Price:",
        price,
        "",
        "Compare At Price:",
        compare_price,
        "",
        "Stock:",
        stock,
        "",
        "Sizes:",
        sizes,
        "",
        "Colors:",
        colors,
        "",
        "Fabric:",
        fabric,
        "",
        "Tags:",
        tags,
        "",
        "-" * 60,
        "DESCRIPTION",
        "-" * 60,
        "",
        description,
        "",
        "-" * 60,
        "DOWNLOADED IMAGES",
        "-" * 60,
        "",
    ]

    if downloaded_images:
        for img_name in downloaded_images:
            lines.append(img_name)
    else:
        lines.append("No images downloaded.")

    if failed_images:
        lines.extend([
            "",
            "-" * 60,
            "FAILED IMAGE DOWNLOADS",
            "-" * 60,
            "",
        ])
        for failed_url, error in failed_images:
            lines.append(f"URL: {failed_url}")
            lines.append(f"ERROR: {error}")
            lines.append("")

    return "\n".join(lines)


# ============================================================
# COLUMN DETECTOR HELPER
# ============================================================

def auto_detect_columns(columns):
    """Best effort match of standard fields to file columns."""
    cols_lower = {str(c).strip().lower(): c for c in columns}

    def match_first(candidates):
        for cand in candidates:
            if cand in cols_lower:
                return cols_lower[cand]
        # Partial match
        for cand in candidates:
            for k in cols_lower:
                if cand in k:
                    return cols_lower[k]
        return None

    return {
        "name": match_first(["name", "product_name", "title", "product title", "product"]),
        "sku": match_first(["sku", "product_sku", "code", "item_code", "id"]),
        "images": match_first(["images", "image", "image_urls", "image_url", "photo", "photos", "img"]),
        "description": match_first(["description", "desc", "body", "product description", "details"]),
        "price": match_first(["price", "sale_price", "regular_price", "amount"]),
        "compare at price": match_first(["compare at price", "compare_price", "old_price", "original_price", "mrp"]),
        "category": match_first(["category", "collection", "product_type", "type"]),
        "brand": match_first(["brand", "vendor", "manufacturer"]),
        "stock": match_first(["stock", "quantity", "inventory", "qty"]),
        "sizes": match_first(["sizes", "size"]),
        "colors": match_first(["colors", "color", "colour"]),
        "fabric": match_first(["fabric", "material"]),
        "tags": match_first(["tags", "tag", "keywords"]),
    }


# ============================================================
# MAIN UI APPLICATION
# ============================================================

def main():
    st.markdown('<div class="main-header">🛍️ Product Image & Info Downloader</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upload a CSV or Excel file to batch download product images and generate organized <code>product_info.txt</code> files for each item.</div>', unsafe_allow_html=True)

    # --------------------------------------------------------
    # SIDEBAR: SETTINGS & CONFIGURATION
    # --------------------------------------------------------
    with st.sidebar:
        st.header("⚙️ Configuration")

        st.subheader("Image Delimiter")
        delimiter = st.selectbox(
            "URLs separator in column:",
            options=["|", ",", ";", "\\n (New Line)", "Auto"],
            index=0,
            help="The character that separates multiple image URLs in each product's image cell.",
        )

        st.subheader("Performance")
        concurrency = st.slider(
            "Parallel download threads:",
            min_value=1,
            max_value=16,
            value=6,
            help="Higher threads will download images faster.",
        )

        timeout = st.number_input("Request timeout (seconds):", min_value=5, max_value=120, value=30)
        retries = st.number_input("Retry attempts:", min_value=1, max_value=5, value=3)

        st.subheader("Destination Mode")
        output_mode = st.radio(
            "Select how to receive files:",
            ["Save to Local Folder", "Download as ZIP Archive (Cloud / Local)"],
            index=0,
        )

        local_dir = "SAWERA_DOWNLOADED"
        if output_mode == "Save to Local Folder":
            local_dir = st.text_input(
                "Local Output Directory:",
                value="SAWERA_DOWNLOADED",
                help="The directory path on your computer where folders will be created.",
            )

    # --------------------------------------------------------
    # STEP 1: FILE UPLOAD
    # --------------------------------------------------------
    uploaded_file = st.file_uploader(
        "Upload your Products CSV or Excel sheet (.csv, .xlsx, .xls)",
        type=["csv", "xlsx", "xls"],
        help="Upload the file containing your product catalog and image links.",
    )

    if uploaded_file is None:
        st.info("👆 Upload a CSV or Excel spreadsheet above to get started.")
        # Provide sample format info
        with st.expander("ℹ️ Supported Format Information"):
            st.markdown(
                """
                - **File types**: `.csv`, `.xlsx`, `.xls`
                - **Essential columns**: `name` (Product Name), `sku` (Product Code/SKU), `images` (Image URLs separated by `|`, commas, or new lines)
                - **Optional columns**: `description`, `price`, `compare at price`, `category`, `brand`, `stock`, `sizes`, `colors`, `fabric`, `tags`
                """
            )
        return

    # Read uploaded file
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, keep_default_na=False)
        else:
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_name = st.selectbox("Select Excel Sheet:", excel_file.sheet_names)
            df = pd.read_excel(uploaded_file, sheet_name=sheet_name, keep_default_na=False)
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return

    if df.empty:
        st.warning("The uploaded file contains no data.")
        return

    # --------------------------------------------------------
    # STEP 2: COLUMN MAPPING & VALIDATION
    # --------------------------------------------------------
    detected = auto_detect_columns(df.columns.tolist())
    all_cols = ["-- None / Ignore --"] + list(df.columns)

    with st.expander("🔍 Column Mapping & Settings (Adjust if needed)", expanded=False):
        st.markdown("Match your file columns to the standard fields below:")
        col1, col2, col3 = st.columns(3)

        def col_index(detected_val):
            if detected_val and detected_val in df.columns:
                return all_cols.index(detected_val)
            return 0

        with col1:
            name_col = st.selectbox("Product Name *:", all_cols, index=col_index(detected["name"]))
            sku_col = st.selectbox("SKU / Code *:", all_cols, index=col_index(detected["sku"]))
            img_col = st.selectbox("Image URLs *:", all_cols, index=col_index(detected["images"]))
            desc_col = st.selectbox("Description:", all_cols, index=col_index(detected["description"]))

        with col2:
            price_col = st.selectbox("Price:", all_cols, index=col_index(detected["price"]))
            comp_price_col = st.selectbox("Compare Price:", all_cols, index=col_index(detected["compare at price"]))
            category_col = st.selectbox("Category:", all_cols, index=col_index(detected["category"]))
            brand_col = st.selectbox("Brand:", all_cols, index=col_index(detected["brand"]))

        with col3:
            stock_col = st.selectbox("Stock:", all_cols, index=col_index(detected["stock"]))
            sizes_col = st.selectbox("Sizes:", all_cols, index=col_index(detected["sizes"]))
            colors_col = st.selectbox("Colors:", all_cols, index=col_index(detected["colors"]))
            fabric_col = st.selectbox("Fabric:", all_cols, index=col_index(detected["fabric"]))
            tags_col = st.selectbox("Tags:", all_cols, index=col_index(detected["tags"]))

    # Validate essential columns
    def get_actual_col(val):
        return None if val == "-- None / Ignore --" else val

    col_map = {
        "name": get_actual_col(name_col),
        "sku": get_actual_col(sku_col),
        "images": get_actual_col(img_col),
        "description": get_actual_col(desc_col),
        "price": get_actual_col(price_col),
        "compare at price": get_actual_col(comp_price_col),
        "category": get_actual_col(category_col),
        "brand": get_actual_col(brand_col),
        "stock": get_actual_col(stock_col),
        "sizes": get_actual_col(sizes_col),
        "colors": get_actual_col(colors_col),
        "fabric": get_actual_col(fabric_col),
        "tags": get_actual_col(tags_col),
    }

    if not col_map["name"] or not col_map["sku"] or not col_map["images"]:
        st.error("⚠️ Please select valid columns for **Product Name**, **SKU**, and **Image URLs**.")
        return

    # --------------------------------------------------------
    # STEP 3: PREVIEW & STATS
    # --------------------------------------------------------
    # Calculate stats
    total_products = len(df)
    total_images = sum(len(split_image_urls(row[col_map["images"]], delimiter)) for _, row in df.iterrows())

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Products", f"{total_products:,}")
    with m2:
        st.metric("Total Image URLs", f"{total_images:,}")
    with m3:
        avg_imgs = round(total_images / max(total_products, 1), 1)
        st.metric("Avg Images / Product", f"{avg_imgs}")
    with m4:
        st.metric("Threads Active", f"{concurrency}")

    # Data preview tab
    tab_preview, tab_info = st.tabs(["📊 Data Preview", "ℹ️ How It Works"])
    with tab_preview:
        st.dataframe(df.head(10), use_container_width=True)
    with tab_info:
        st.markdown(
            """
            **Each product folder will include:**
            1. Downloaded images sequentially named (`01.webp`, `02.jpg`, etc.)
            2. `product_info.txt` containing full details (Name, SKU, Price, Description, Sizes, Fabric, etc.)
            3. A master `DOWNLOAD_SUMMARY.txt` with statistics and any failed URLs.
            """
        )

    # --------------------------------------------------------
    # STEP 4: DOWNLOAD EXECUTION
    # --------------------------------------------------------
    st.write("---")
    c_start, c_range = st.columns([1, 2])

    with c_range:
        enable_range = st.checkbox("Download specific product row range (optional)", value=False)
        if enable_range:
            r1, r2 = st.columns(2)
            with r1:
                start_row = st.number_input("From Row #:", min_value=1, max_value=total_products, value=1)
            with r2:
                end_row = st.number_input("To Row #:", min_value=1, max_value=total_products, value=total_products)
            active_df = df.iloc[int(start_row) - 1 : int(end_row)]
        else:
            active_df = df

    with c_start:
        start_btn = st.button("🚀 Start Download Process", type="primary", use_container_width=True)

    if start_btn:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        log_box = st.empty()
        
        # Working folder setup
        if output_mode == "Save to Local Folder":
            dest_root = Path(local_dir)
            dest_root.mkdir(parents=True, exist_ok=True)
        else:
            # Temporary folder for ZIP creation
            temp_dir = tempfile.TemporaryDirectory()
            dest_root = Path(temp_dir.name) / "DOWNLOADED_PRODUCTS"
            dest_root.mkdir(parents=True, exist_ok=True)

        successful_images = 0
        failed_images_count = 0
        failed_products = []
        logs = []

        total_active_products = len(active_df)

        def log_msg(msg):
            logs.append(msg)
            # Display last 8 lines
            display_logs = "\n".join(logs[-8:])
            log_box.code(display_logs, language="bash")

        log_msg(f"[*] Starting download of {total_active_products} products...")

        # Process each product
        for idx, (_, row) in enumerate(active_df.iterrows(), start=1):
            product_name = clean_value(row[col_map["name"]], "Product")
            sku = clean_value(row[col_map["sku"]], "SKU")
            
            folder_name = f"{clean_filename(sku)}_{clean_filename(product_name)}"
            product_folder = dest_root / folder_name
            product_folder.mkdir(parents=True, exist_ok=True)

            raw_imgs = row[col_map["images"]]
            urls = split_image_urls(raw_imgs, delimiter)

            downloaded_images = []
            failed_images = []

            status_text.markdown(f"**Processing ({idx}/{total_active_products}):** `{sku}` - {product_name[:40]}...")

            # Helper for thread worker
            def download_worker(url_info):
                img_idx, url = url_info
                base_name = product_folder / f"{img_idx:02d}"
                ok, res_name, err = download_single_image(url, base_name, timeout=timeout, retries=retries)
                return ok, res_name, err, url

            # Parallel download for images of this product
            if urls:
                with ThreadPoolExecutor(max_workers=min(concurrency, len(urls))) as executor:
                    futures = [executor.submit(download_worker, (i, url)) for i, url in enumerate(urls, start=1)]
                    for future in as_completed(futures):
                        ok, res_name, err, url = future.result()
                        if ok:
                            downloaded_images.append(res_name)
                            successful_images += 1
                        else:
                            failed_images.append((url, err))
                            failed_images_count += 1

            # Sort downloaded images naturally
            downloaded_images.sort()

            # Create product_info.txt
            info_txt = create_product_info_text(row, col_map, downloaded_images, failed_images)
            with open(product_folder / "product_info.txt", "w", encoding="utf-8") as f:
                f.write(info_txt)

            if failed_images:
                failed_products.append({
                    "Product": product_name,
                    "SKU": sku,
                    "Failed Images": len(failed_images),
                })
                log_msg(f"[!] {sku}: {len(downloaded_images)} ok, {len(failed_images)} failed")
            else:
                log_msg(f"[+] {sku}: {len(downloaded_images)} images downloaded")

            progress_bar.progress(idx / total_active_products)

        # Create master summary
        summary_lines = [
            "=" * 70,
            "DOWNLOAD SUMMARY REPORT",
            "=" * 70,
            f"Total Products Processed: {total_active_products}",
            f"Successfully Downloaded Images: {successful_images}",
            f"Failed Image Downloads: {failed_images_count}",
            "",
            "-" * 70,
            "FAILED PRODUCTS DETAILS",
            "-" * 70,
        ]
        if failed_products:
            for item in failed_products:
                summary_lines.append(f"SKU: {item['SKU']} | Product: {item['Product']} | Failed Images: {item['Failed Images']}")
        else:
            summary_lines.append("All images downloaded successfully without errors.")

        summary_file = dest_root / "DOWNLOAD_SUMMARY.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_lines))

        status_text.markdown("✅ **Download complete!**")
        st.success("🎉 Process finished successfully!")

        # Show final metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Products Done", total_active_products)
        c2.metric("Images Downloaded", successful_images)
        c3.metric("Failed Images", failed_images_count)

        # Download ZIP button if Zip mode or for convenience
        if output_mode == "Save to Local Folder":
            st.info(f"📂 Files saved locally to: `{dest_root.resolve()}`")
        else:
            st.write("📦 Packaging files into ZIP archive...")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(dest_root):
                    for file in files:
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(dest_root)
                        zipf.write(full_path, arcname=str(rel_path))
            
            zip_buffer.seek(0)
            st.download_button(
                label="⬇️ Download All as ZIP Archive",
                data=zip_buffer,
                file_name="product_catalog_downloaded.zip",
                mime="application/zip",
                type="primary",
            )


if __name__ == "__main__":
    main()
