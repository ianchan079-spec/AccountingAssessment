import streamlit as st
import pandas as pd
import json
import os
import csv
from generator import AccountancyGenerator
from auditor import Auditor

LEADERBOARD_FILE = "leaderboard.json"
RESEARCH_LOG_FILE = "research_logs.csv"
TRIMESTER_CODE = "T1_2026"

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, "r") as f:
            return json.load(f)
    return []

def save_leaderboard(data):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f)

def log_submission(student_id, score, feedback):
    # Check current attempts
    attempt = 1
    if os.path.exists(RESEARCH_LOG_FILE):
        with open(RESEARCH_LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Student_ID") == student_id:
                    attempt += 1
    
    file_exists = os.path.exists(RESEARCH_LOG_FILE)
    errors = " | ".join([fb for fb in feedback if not fb.startswith("✅")])
    
    with open(RESEARCH_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Student_ID", "Attempt_Number", "Score", "Specific_Errors"])
        writer.writerow([student_id, attempt, score, errors])

def calculate_profit(df: pd.DataFrame) -> float:
    """Calculates Net Income from the trial balance."""
    revenues = ['Service Revenue', 'Interest Revenue']
    expenses = ['Salaries Expense', 'Utilities Expense', 'Miscellaneous Expense', 
                'Interest Expense', 'Supplies Expense', 'Rent Expense', 'Depreciation Expense']
    
    profit = 0.0
    for _, row in df.iterrows():
        acc = row.get('Account', '')
        # Convert values to float safely
        try:
            debit = float(str(row.get('Debit', 0)).replace(',', '')) if pd.notna(row.get('Debit')) and str(row.get('Debit')).strip() else 0.0
            credit = float(str(row.get('Credit', 0)).replace(',', '')) if pd.notna(row.get('Credit')) and str(row.get('Credit')).strip() else 0.0
        except ValueError:
            continue
            
        if acc in revenues:
            profit += credit - debit
        elif acc in expenses:
            profit -= debit - credit
            
    return profit

st.set_page_config(page_title="Accountancy Capstone", layout="wide")

with st.sidebar:
    st.header("Materials")
    try:
        with open("student_manual.txt", "rb") as f:
            st.download_button(
                label="📥 Download Manual",
                data=f,
                file_name="student_manual.txt",
                mime="text/plain"
            )
    except FileNotFoundError:
        st.error("Manual not found on server.")

st.title("📊 Accountancy Capstone Simulation")

tab1, tab2, tab3, tab4 = st.tabs(["📋 Tab 1: Setup", "📤 Tab 2: Submission", "🏆 Tab 3: Results & Leaderboard", "📖 Tab 4: Xero Guide"])

with tab1:
    st.header("Case Setup")
    st.write("Enter your Student ID to generate your unique business scenario.")
    
    student_id = st.text_input("Student ID (e.g., SIT12345)")
    
    if student_id:
        generator = AccountancyGenerator(student_id, TRIMESTER_CODE)
        generator.generate()
        
        st.success(f"Generated case for {student_id}!")
        
        st.subheader("Your Unique Business Transactions (Month 1)")
        for text in generator.transactions_text:
            st.write(text)
            
        st.subheader("Download Template")
        st.write("Use this standardized Chart of Accounts for your Trial Balance to ensure proper grading. Using ad-hoc account names is poor practice and will fail the audit.")
        
        try:
            with open("coa_template.csv", "rb") as f:
                st.download_button(
                    label="Download COA Template (CSV)",
                    data=f,
                    file_name="coa_template.csv",
                    mime="text/csv"
                )
        except FileNotFoundError:
            st.error("Template file not found on server.")

with tab2:
    st.header("Upload Submission Files")
    st.write("Upload your completed Trial Balance CSV and your Xero Journal Report (PDF). Both are required.")
    
    uploaded_csv = st.file_uploader("Choose Trial Balance CSV", type=["csv"])
    uploaded_pdf = st.file_uploader("Choose Xero Journal Report PDF", type=["pdf"])
    
    if uploaded_csv and uploaded_pdf and student_id:
        try:
            student_df = pd.read_csv(uploaded_csv)
            st.session_state['student_df'] = student_df
            st.session_state['student_id'] = student_id
            st.session_state['pdf_uploaded'] = True
            st.success("Files uploaded successfully. Proceed to Tab 3 for results.")
            st.dataframe(student_df.head(10))
        except Exception as e:
            st.error(f"Error reading file: {e}")
    elif (uploaded_csv or uploaded_pdf) and not student_id:
        st.warning("Please enter your Student ID in Tab 1 first.")
    elif uploaded_csv and not uploaded_pdf:
        st.warning("Please also upload your Xero Journal Report (PDF) to proceed.")

with tab3:
    st.header("Results & Leaderboard")
    
    if st.button("Run Master Auditor"):
        if 'student_df' in st.session_state and 'student_id' in st.session_state and st.session_state.get('pdf_uploaded', False):
            active_id = st.session_state['student_id']
            active_df = st.session_state['student_df']
            
            auditor = Auditor(active_id)
            score, feedback = auditor.audit(active_df)
            
            profit = calculate_profit(active_df)
            
            st.subheader(f"Score: {score:.1f}%")
            if score >= 90:
                st.balloons()
                
            st.write(f"**Calculated Profit (Net Income):** ${profit:,.2f}")
            
            st.subheader("Audit Feedback")
            for fb in feedback:
                st.write(fb)
                
            # Log the attempt for research
            log_submission(active_id, score, feedback)
                
            # Update Leaderboard
            leaderboard = load_leaderboard()
            # Remove old entry if exists
            leaderboard = [entry for entry in leaderboard if entry['student_id'] != active_id]
            leaderboard.append({'student_id': active_id, 'score': score, 'profit': profit})
            
            # Sort: First by score (desc), then by profit (desc)
            leaderboard.sort(key=lambda x: (x['score'], x['profit']), reverse=True)
            leaderboard = leaderboard[:10] # Top 10
            
            save_leaderboard(leaderboard)
        else:
            st.warning("Incomplete submission. Please upload both the Trial Balance CSV and Xero Journal Report PDF in Tab 2.")
            
    st.markdown("---")
    st.subheader("🏆 Top 10 Leaderboard")
    lb_data = load_leaderboard()
    
    if lb_data:
        lb_df = pd.DataFrame(lb_data)
        lb_df.index = lb_df.index + 1
        st.table(lb_df)
    else:
        st.write("No entries yet.")

with tab4:
    st.header("Xero Quick Start Guide")
    
    st.markdown("""
### Phase 1: Setup
1. **Sign Up**: Create a free 30-day Xero trial account.
2. **Organization Name**: You MUST name your organization using the format: `[Student ID] - [Full Name] Consultancy`.
3. **Import COA**: Go to `Accounting > Advanced > Chart of Accounts` and use the "Import" function with the CSV template downloaded from this portal.

### Phase 2: Recording Entries
1. **Operational**: Record daily sales invoices and bills under `Business > Invoices/Bills`.
2. **Journal Entries**: For the Loan (TVM) and Adjusting Entries, use `Accounting > Reports > Journal Report > Add New Journal`.
3. **Note**: Ensure your Jan 31st interest accrual journal entry matches your TVM calculations exactly.

### Phase 3: The Export (Submission)
1. Go to `Accounting > Reports > Trial Balance`.
2. Select the date: **31 Jan 2026**.
3. Click `Export > CSV`.
4. **Crucial**: Open the CSV and ensure the column headers match the "COA Template" before uploading to the portal.
5. **Verification**: Export the "Detailed Journal Report" from Xero as a PDF. Both files are required for submission.
    """)
