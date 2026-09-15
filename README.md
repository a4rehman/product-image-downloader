# 🛍️ Product Image & Info Downloader (Streamlit App)

A web application built with Streamlit to batch download product images and automatically generate detailed `product_info.txt` specifications from any CSV or Excel spreadsheet.

---

## 🚀 Features

- **Multi-Format Support**: Upload `.csv`, `.xlsx`, or `.xls` spreadsheets.
- **Smart Column Detection**: Automatically detects column names like `name`, `sku`, `images`, `description`, `price`, `sizes`, `colors`, etc., with full custom mapping override.
- **Multi-threaded Fast Downloading**: Configurable parallel workers for fast downloading.
- **Dual Destination Modes**:
  1. **Local Folder**: Directly saves organized folders (`SKU_ProductName`) on your computer.
  2. **ZIP Archive Download**: Packages all folders into a single `.zip` file — works seamlessly on **Streamlit Cloud** or remote servers.
- **Detailed Specifications**: Generates `product_info.txt` inside every product folder and a master `DOWNLOAD_SUMMARY.txt`.

---

## 💻 How to Run Locally

1. Open your terminal in this directory:
   ```bash
   cd K:\portfolio_website\image_downloader
   ```

2. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

3. Open the displayed local URL in your web browser (usually `http://localhost:8501`).

---

## ☁️ How to Deploy on Streamlit Cloud (Free)

1. Push this folder to a **GitHub repository** (e.g., `image-downloader`).
2. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with GitHub.
3. Click **"New app"**.
4. Select your repository, branch (`main`), and set the main file path to:
   ```text
   app.py
   ```
5. Click **"Deploy"**!
