import pandas as pd
from typing import Dict, Any, Tuple
from generator import AccountancyGenerator

class Auditor:
    def __init__(self, student_id: str):
        self.student_id = student_id.upper()
        self.generator = AccountancyGenerator(self.student_id)
        self.generator.generate()
        self.truth_df = self.generator.get_ground_truth()
        
        # Define categories for weighted grading
        self.tvm_adj_accounts = [
            'Notes Payable', 'Interest Expense', 'Interest Receivable', 
            'Interest Revenue', 'Short-Term Investments', 'Supplies Expense', 
            'Prepaid Rent', 'Rent Expense', 'Depreciation Expense', 
            'Accumulated Depreciation', 'Salaries Payable',
            'Prepaid Insurance', 'Insurance Expense'
        ]
        
        self.op_accounts = [
            'Cash', 'Accounts Receivable', 'Accounts Payable', 
            'Service Revenue', 'Salaries Expense', 'Utilities Expense', 
            'Common Stock', 'Equipment', 'Dividends', 
            'Miscellaneous Expense', 'Supplies', 'Advertising Expense'
        ]

    def audit(self, student_df: pd.DataFrame) -> Tuple[float, list]:
        """
        Takes student_df (expected columns: Account, Debit, Credit)
        Returns: (overall_score (0-100), list of feedback messages)
        """
        feedback = []
        
        # Clean student dataframe
        if not {'Account', 'Debit', 'Credit'}.issubset(student_df.columns):
            return 0.0, ["Error: Uploaded CSV missing 'Account', 'Debit', or 'Credit' columns."]
            
        student_df = student_df.fillna(0)
        
        # Convert true df to dictionary of account -> balance (positive for debit, negative for credit)
        truth_dict = {}
        for _, row in self.truth_df.iterrows():
            truth_dict[str(row['Account']).strip().upper()] = round(row['Debit'] - row['Credit'], 2)
            
        # Convert student df to dictionary
        student_dict = {}
        for _, row in student_df.iterrows():
            acc_key = str(row['Account']).strip().upper()
            d_val = row['Debit']
            c_val = row['Credit']
            
            debit = 0.0
            if pd.notna(d_val):
                d_str = str(d_val).replace(',', '').replace('$', '').strip()
                if d_str: debit = float(d_str)
                
            credit = 0.0
            if pd.notna(c_val):
                c_str = str(c_val).replace(',', '').replace('$', '').strip()
                if c_str: credit = float(c_str)
                
            student_dict[acc_key] = round(debit - credit, 2)
            
        # Scoring variables
        tvm_adj_correct = 0
        tvm_adj_total = len(self.tvm_adj_accounts)
        
        op_correct = 0
        op_total = len(self.op_accounts)
        
        # Evaluate all accounts
        all_accounts = self.tvm_adj_accounts + self.op_accounts
        upper_standard_coa = [a.upper() for a in all_accounts]
        
        # Check for unmapped student accounts
        for student_acc, val in student_dict.items():
            if abs(val) > 0 and student_acc not in upper_standard_coa:
                feedback.append(f"❌ '{student_acc}': Invalid Account Name: Please refer to the standardized Chart of Accounts.")
        
        for acc in all_accounts:
            acc_key = acc.strip().upper()
            expected = truth_dict.get(acc_key, 0.0)
            actual = student_dict.get(acc_key, 0.0)
            
            print(f"Comparing '{acc}': Student [{actual}] vs Ground Truth [{expected}]")
            
            is_correct = (abs(expected - actual) <= 0.05) # Add small tolerance for float issues
            
            if acc in self.tvm_adj_accounts:
                if is_correct:
                    tvm_adj_correct += 1
                else:
                    exp_type = "Debit" if expected > 0 else "Credit" if expected < 0 else "Zero"
                    feedback.append(f"❌ {acc}: Incorrect balance. Expected a {exp_type} balance.")
            else:
                if is_correct:
                    op_correct += 1
                else:
                    exp_type = "Debit" if expected > 0 else "Credit" if expected < 0 else "Zero"
                    feedback.append(f"❌ {acc}: Incorrect balance. Expected a {exp_type} balance.")
                    
        # --- Specific Pedagogical Feedback ---
        # TVM Interest Expense check
        notes_payable_expected = truth_dict.get('NOTES PAYABLE', 0.0)
        notes_payable_actual = student_dict.get('NOTES PAYABLE', 0.0)
        int_exp_expected = truth_dict.get('INTEREST EXPENSE', 0.0)
        int_exp_actual = student_dict.get('INTEREST EXPENSE', 0.0)
        
        # If Notes Payable is right (or close) but Interest Expense is wrong
        if abs(notes_payable_expected - notes_payable_actual) <= 0.05 and abs(int_exp_expected - int_exp_actual) > 0.05:
             feedback.append("💡 Pedagogical Note: Your loan principal (Notes Payable) is correct, but your Interest Expense accrual is incorrect. Check your TVM calculation for PMT and ensure you split out interest vs. principal properly for the first payment.")

        # Depreciation logic check
        equip_expected = truth_dict.get('EQUIPMENT', 0.0)
        equip_actual = student_dict.get('EQUIPMENT', 0.0)
        depr_exp_expected = truth_dict.get('DEPRECIATION EXPENSE', 0.0)
        depr_exp_actual = student_dict.get('DEPRECIATION EXPENSE', 0.0)
        
        if abs(equip_expected - equip_actual) <= 0.05 and abs(depr_exp_expected - depr_exp_actual) > 0.05:
             feedback.append("💡 Pedagogical Note: The Equipment cost is correct, but Depreciation Expense is incorrect. Remember the policy: 5 years straight-line, zero salvage value. Calculate (Cost / (5 * 12)).")

        # Adjusting supplies check
        supplies_expected = truth_dict.get('SUPPLIES', 0.0)
        supplies_actual = student_dict.get('SUPPLIES', 0.0)
        supplies_exp_expected = truth_dict.get('SUPPLIES EXPENSE', 0.0)
        supplies_exp_actual = student_dict.get('SUPPLIES EXPENSE', 0.0)

        if abs(supplies_expected - supplies_actual) > 0.05 and abs(supplies_exp_expected - supplies_exp_actual) > 0.05:
            # Maybe they missed the adjusting entry entirely?
            if abs(supplies_exp_actual) <= 0.05 and abs(supplies_exp_expected) > 0:
                 feedback.append("💡 Pedagogical Note: It looks like you missed the adjusting entry for Supplies at month-end. You must move the amount used from the Asset to the Expense.")


        # --- Calculate Final Score ---
        # Weighting: 40% TVM/Adj, 60% Operational
        tvm_adj_score = (tvm_adj_correct / tvm_adj_total) * 40 if tvm_adj_total > 0 else 40
        op_score = (op_correct / op_total) * 60 if op_total > 0 else 60
        
        total_score = round(tvm_adj_score + op_score, 2)
        
        if total_score == 100.0:
            feedback.insert(0, "✅ Perfect Trial Balance! All accounts are accurate.")
            
        feedback.append("If your balances match but your Xero Journal Report is missing, your submission will be considered incomplete.")
            
        return total_score, feedback
