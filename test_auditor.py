from generator import AccountancyGenerator
from auditor import Auditor
import pandas as pd
import numpy as np

# Test 1: Perfect Upload
student_id = "SIT12345"
gen = AccountancyGenerator(student_id)
gen.generate()
perfect_df = gen.get_ground_truth()

auditor = Auditor(student_id)
perfect_score, perfect_feedback = auditor.audit(perfect_df)
print(f"Perfect Score: {perfect_score}")
print(f"Perfect Feedback: {perfect_feedback}")

# Test 2: Flawed Upload (TVM error)
flawed_df = perfect_df.copy()
# Find Interest Expense and alter it
int_idx = flawed_df[flawed_df['Account'] == 'Interest Expense'].index
if len(int_idx) > 0:
    flawed_df.loc[int_idx[0], 'Debit'] += 50.0 # Make it slightly wrong

# Find Equipment and Depreciation
eq_idx = flawed_df[flawed_df['Account'] == 'Accumulated Depreciation'].index
if len(eq_idx) > 0:
    flawed_df.loc[eq_idx[0], 'Credit'] -= 100.0

flawed_score, flawed_feedback = auditor.audit(flawed_df)
print(f"\nFlawed Score: {flawed_score}")
print(f"Flawed Feedback: {flawed_feedback}")
