from generator import AccountancyGenerator

student_id = "SIT12345"
trimester_code = "T1_2026"

generator = AccountancyGenerator(student_id, trimester_code)
generator.generate()

print(f"--- Transaction Pool Generation: {len(generator.transactions_text)} Events ---")
for text in generator.transactions_text:
    print(text)

print("\n--- Verification Ground Truth ---")
tb = generator.get_ground_truth()
print(tb)
print(f"Total Debits: {tb['Debit'].sum():.2f}")
print(f"Total Credits: {tb['Credit'].sum():.2f}")
