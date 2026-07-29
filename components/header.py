"""
components/header.py — Application header banner.
"""
import streamlit as st


def render_header(subtitle: str = "Upload your reports · Analyse performance · Plan for growth") -> None:
    st.markdown(f"""
    <div class="tool-header">
        <div>
            <div class="tool-header-title">📊 Amazon Media Plan Forecast Engine</div>
            <div class="tool-header-sub">{subtitle}</div>
        </div>
        <div class="tool-header-badge">Media Intelligence</div>
    </div>""", unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown("""
    <div class="tool-footer">
        Amazon Media Plan Forecast Engine &nbsp;&#183;&nbsp;
        Created by <strong>Sumeet Mangotra</strong>, Brand Ecommerce Manager
    </div>""", unsafe_allow_html=True)


def render_welcome() -> None:
    st.markdown("""
    <div class="welcome-box">
        <div style="font-size:20px;font-weight:800;color:#1a0a14;margin-bottom:20px;">
            👋 Welcome — Upload your reports to get started
        </div>
        <div class="welcome-step">
            <div class="step-icon">1</div>
            <div class="step-text">
                <strong>Upload your Amazon Advertising Report</strong>
                <span>Ads Console → Reports → Sponsored Products / Brands / Display &nbsp;(CSV or XLSX, up to 3 GB)</span>
            </div>
        </div>
        <div class="welcome-step">
            <div class="step-icon">2</div>
            <div class="step-text">
                <strong>Upload your Vendor Central ASIN Sales Report</strong>
                <span>Vendor Central → Analytics → Sales Diagnostics &nbsp;(CSV or XLSX)</span>
            </div>
        </div>
        <div class="welcome-step">
            <div class="step-icon">3</div>
            <div class="step-text">
                <strong>Get 6 insight tabs instantly</strong>
                <span>Key Metrics &nbsp;·&nbsp; Product Intelligence &nbsp;·&nbsp; Trend Analysis &nbsp;·&nbsp;
                Forecast &amp; Media Plan &nbsp;·&nbsp; Recommendations &nbsp;·&nbsp; How It Works</span>
            </div>
        </div>
        <div class="welcome-step">
            <div class="step-icon">4</div>
            <div class="step-text">
                <strong>Model growth scenarios</strong>
                <span>+10%, +20%, +30% and custom — get recommended ad spend, channel split, and per-campaign budget actions</span>
            </div>
        </div>
        <div class="welcome-step">
            <div class="step-icon">5</div>
            <div class="step-text">
                <strong>Download a full Excel Media Plan</strong>
                <span>5-sheet workbook — Executive Summary, Scenarios, Campaign Recommendations, Campaign Performance, ASIN Analysis</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)
