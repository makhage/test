"""Custom CSS injection, branding, and responsive layout for the Streamlit dashboard."""

CUSTOM_CSS = """
<style>
/* Import Google Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Global font */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Main container */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    border-right: 1px solid #334155;
}

[data-testid="stSidebar"] .css-1d391kg {
    padding-top: 2rem;
}

/* Card styling */
.card {
    background: #1E293B;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    border: 1px solid #334155;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 15px -3px rgba(0, 0, 0, 0.4);
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1E293B 0%, #334155 100%);
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
    border: 1px solid #475569;
}

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #6366F1;
    margin: 0;
}

.metric-label {
    font-size: 0.85rem;
    color: #94A3B8;
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Status badges */
.badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
}

.badge-pending { background: #F59E0B20; color: #F59E0B; border: 1px solid #F59E0B40; }
.badge-approved { background: #10B98120; color: #10B981; border: 1px solid #10B98140; }
.badge-published { background: #6366F120; color: #6366F1; border: 1px solid #6366F140; }
.badge-rejected { background: #EF444420; color: #EF4444; border: 1px solid #EF444440; }
.badge-draft { background: #64748B20; color: #64748B; border: 1px solid #64748B40; }

/* Platform badges */
.platform-twitter { background: #1DA1F220; color: #1DA1F2; }
.platform-instagram { background: #E4405F20; color: #E4405F; }
.platform-tiktok { background: #00F2EA20; color: #00F2EA; }

/* Toast notifications */
.toast {
    position: fixed;
    top: 1rem;
    right: 1rem;
    background: #10B981;
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    z-index: 9999;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

/* Table styling */
.stDataFrame {
    border-radius: 8px;
    overflow: hidden;
}

/* Button styling */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5rem 1.5rem;
    transition: all 0.2s;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 0.5rem 1rem;
}

/* Responsive columns */
@media (max-width: 768px) {
    .main .block-container {
        padding: 1rem;
    }
    .metric-value {
        font-size: 1.5rem;
    }
}

/* Expander */
.streamlit-expanderHeader {
    border-radius: 8px;
    background: #1E293B;
}

/* Progress bar */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #6366F1, #EC4899);
}

/* Logo in sidebar */
.sidebar-logo {
    text-align: center;
    padding: 1rem 0 2rem 0;
    border-bottom: 1px solid #334155;
    margin-bottom: 1rem;
}

.sidebar-logo h1 {
    font-size: 1.5rem;
    background: linear-gradient(135deg, #6366F1, #EC4899);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
</style>
"""


def inject_custom_css() -> None:
    """Inject custom CSS into the Streamlit app."""
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_metric_card(label: str, value: str | int, delta: str = "") -> str:
    """Return HTML for a styled metric card."""
    delta_html = f'<p style="color: #10B981; font-size: 0.8rem; margin: 0;">{delta}</p>' if delta else ""
    return f"""
    <div class="metric-card">
        <p class="metric-value">{value}</p>
        <p class="metric-label">{label}</p>
        {delta_html}
    </div>
    """


def render_status_badge(status: str) -> str:
    """Return HTML for a status badge."""
    return f'<span class="badge badge-{status.lower()}">{status}</span>'


def render_platform_badge(platform: str) -> str:
    """Return HTML for a platform badge."""
    return f'<span class="badge platform-{platform.lower()}">{platform}</span>'
