"""
Library Management System — Streamlit frontend.

Run with:
    pip install streamlit pandas
    streamlit run app.py

Data is stored in library.json (same format as the original console app),
so existing library files keep working.
"""

import json
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

FILE_NAME = "library.json"
LOAN_DAYS = 14


# ---------------------------------------------------------------------------
# Data layer (same logic as the console version, but returns results instead
# of printing so the UI can display them)
# ---------------------------------------------------------------------------
def load_data():
    try:
        with open(FILE_NAME, "r") as file:
            library = json.load(file)
            if not isinstance(library, dict):
                st.warning("Invalid library data. Starting with an empty library.")
                return {}
            return library
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        st.warning("library.json is corrupted. Starting with an empty library.")
        return {}


def save_data(library):
    try:
        with open(FILE_NAME, "w") as file:
            json.dump(library, file, indent=4)
        return True
    except OSError as error:
        st.error(f"Error saving library: {error}")
        return False


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def days_late(book, today=None):
    if book["available"] or not book.get("due_date"):
        return 0
    today = today or date.today()
    return (today - parse_date(book["due_date"])).days


def add_book(library, book_id, title, author):
    book_id = book_id.strip().upper()
    title, author = title.strip(), author.strip()
    if not book_id or not title or not author:
        return False, "All fields are required."
    if book_id in library:
        return False, "This book ID already exists."
    library[book_id] = {
        "title": title,
        "author": author,
        "available": True,
        "issued_to": None,
        "issue_date": None,
        "due_date": None,
    }
    save_data(library)
    return True, f'Book "{title}" added successfully.'


def issue_book(library, book_id, member):
    member = member.strip()
    if book_id not in library:
        return False, "Book ID does not exist."
    if not member:
        return False, "Member name cannot be empty."
    book = library[book_id]
    if not book["available"]:
        return False, "This book is already issued."
    issue_date = date.today()
    due_date = issue_date + timedelta(days=LOAN_DAYS)
    book.update(
        available=False,
        issued_to=member,
        issue_date=issue_date.isoformat(),
        due_date=due_date.isoformat(),
    )
    save_data(library)
    return True, f'Book "{book["title"]}" issued to {member}. Due date: {due_date}'


def return_book(library, book_id):
    if book_id not in library:
        return False, "Book ID does not exist.", 0
    book = library[book_id]
    if book["available"]:
        return False, "This book is not currently issued.", 0
    late = days_late(book)
    msg = f'Book "{book["title"]}" returned by {book["issued_to"]}.'
    book.update(available=True, issued_to=None, issue_date=None, due_date=None)
    save_data(library)
    return True, msg, late


def books_dataframe(library):
    rows = []
    for book_id, book in library.items():
        late = days_late(book)
        if book["available"]:
            status = "Available"
        elif late > 0:
            status = f"Overdue ({late}d)"
        else:
            status = "Issued"
        rows.append(
            {
                "Book ID": book_id,
                "Title": book["title"],
                "Author": book["author"],
                "Status": status,
                "Issued to": book["issued_to"] or "—",
                "Issue date": book["issue_date"] or "—",
                "Due date": book["due_date"] or "—",
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Library Manager", page_icon="📚", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; }
      div[data-testid="stMetric"] {
          background: rgba(120,120,120,0.08);
          border: 1px solid rgba(120,120,120,0.2);
          border-radius: 12px;
          padding: 12px 16px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

library = load_data()

# Sidebar navigation
st.sidebar.title("📚 Library Manager")
page = st.sidebar.radio(
    "Menu",
    [
        "🏠 Dashboard",
        "➕ Add book",
        "📖 View all books",
        "🔍 Search books",
        "📤 Issue book",
        "📥 Return book",
        "⏰ Overdue books",
    ],
    label_visibility="collapsed",
)
st.sidebar.divider()
st.sidebar.caption(f"Data file: `{FILE_NAME}`")
st.sidebar.caption(f"Loan period: {LOAN_DAYS} days")

# Shared stats
total = len(library)
available = sum(1 for b in library.values() if b["available"])
issued = total - available
overdue = sum(1 for b in library.values() if days_late(b) > 0)


def status_color(val):
    if val == "Available":
        return "color: #16a34a; font-weight: 600"
    if str(val).startswith("Overdue"):
        return "color: #dc2626; font-weight: 600"
    return "color: #d97706; font-weight: 600"


def show_table(df):
    if df.empty:
        st.info("No books to show.")
        return
    st.dataframe(
        df.style.map(status_color, subset=["Status"]),
        width="stretch",
        hide_index=True,
    )


# ---- Dashboard -------------------------------------------------------------
if page == "🏠 Dashboard":
    st.title("Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total books", total)
    c2.metric("Available", available)
    c3.metric("Issued", issued)
    c4.metric("Overdue", overdue)

    st.subheader("Recently issued")
    df = books_dataframe(library)
    if not df.empty:
        df = df[df["Status"] != "Available"].sort_values("Due date")
    show_table(df)

# ---- Add book --------------------------------------------------------------
elif page == "➕ Add book":
    st.title("Add a new book")
    with st.form("add_form", clear_on_submit=True):
        book_id = st.text_input("Book ID", placeholder="e.g. B001")
        title = st.text_input("Title")
        author = st.text_input("Author")
        submitted = st.form_submit_button("Add book", type="primary")
    if submitted:
        ok, msg = add_book(library, book_id, title, author)
        (st.success if ok else st.error)(msg)

# ---- View all --------------------------------------------------------------
elif page == "📖 View all books":
    st.title("All books")
    if not library:
        st.info("No books available in the library.")
    else:
        filt = st.segmented_control(
            "Filter", ["All", "Available", "Issued", "Overdue"], default="All"
        )
        df = books_dataframe(library)
        if filt == "Available":
            df = df[df["Status"] == "Available"]
        elif filt == "Issued":
            df = df[df["Status"] != "Available"]
        elif filt == "Overdue":
            df = df[df["Status"].str.startswith("Overdue")]
        show_table(df)

# ---- Search ----------------------------------------------------------------
elif page == "🔍 Search books":
    st.title("Search books")
    if not library:
        st.info("Library is empty.")
    else:
        query = st.text_input("Search by title or author", placeholder="Type to search…")
        if query.strip():
            q = query.strip().lower()
            matches = {
                k: v
                for k, v in library.items()
                if q in v["title"].lower() or q in v["author"].lower()
            }
            if matches:
                st.caption(f"{len(matches)} result(s)")
                show_table(books_dataframe(matches))
            else:
                st.warning("No matching books found.")

# ---- Issue -----------------------------------------------------------------
elif page == "📤 Issue book":
    st.title("Issue a book")
    options = {
        k: f'{k} — {v["title"]} by {v["author"]}'
        for k, v in library.items()
        if v["available"]
    }
    if not options:
        st.info("No available books to issue.")
    else:
        with st.form("issue_form", clear_on_submit=True):
            book_id = st.selectbox(
                "Book", list(options), format_func=lambda k: options[k]
            )
            member = st.text_input("Member name")
            st.caption(
                f"Due date will be {date.today() + timedelta(days=LOAN_DAYS)}"
            )
            submitted = st.form_submit_button("Issue book", type="primary")
        if submitted:
            ok, msg = issue_book(library, book_id, member)
            (st.success if ok else st.error)(msg)

# ---- Return ----------------------------------------------------------------
elif page == "📥 Return book":
    st.title("Return a book")
    options = {
        k: f'{k} — {v["title"]} (issued to {v["issued_to"]}, due {v["due_date"]})'
        for k, v in library.items()
        if not v["available"]
    }
    if not options:
        st.info("No books are currently issued.")
    else:
        with st.form("return_form"):
            book_id = st.selectbox(
                "Book", list(options), format_func=lambda k: options[k]
            )
            submitted = st.form_submit_button("Return book", type="primary")
        if submitted:
            ok, msg, late = return_book(library, book_id)
            if ok:
                if late > 0:
                    st.warning(f"Book is {late} day(s) overdue.")
                else:
                    st.info("Book returned on time.")
                st.success(msg + " Book returned successfully.")
            else:
                st.error(msg)

# ---- Overdue ---------------------------------------------------------------
elif page == "⏰ Overdue books":
    st.title("Overdue books")
    rows = [
        {
            "Book ID": k,
            "Title": v["title"],
            "Issued to": v["issued_to"],
            "Due date": v["due_date"],
            "Days late": days_late(v),
        }
        for k, v in library.items()
        if days_late(v) > 0
    ]
    if not rows:
        st.success("No overdue books. 🎉")
    else:
        df = pd.DataFrame(rows).sort_values("Days late", ascending=False)
        st.dataframe(df, width="stretch", hide_index=True)
