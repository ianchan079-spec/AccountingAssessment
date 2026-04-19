import hashlib
import random
import pandas as pd
import numpy_financial as npf

def get_seed_from_id(student_id: str, trimester_code: str) -> int:
    """Produces a deterministic integer seed from a string and trimester."""
    combined = f"{student_id}_{trimester_code}"
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return int(hash_obj.hexdigest()[:16], 16)

class AccountancyGenerator:
    STANDARD_COA = [
        "Cash", "Short-Term Investments", "Accounts Receivable", "Interest Receivable", 
        "Supplies", "Prepaid Rent", "Prepaid Insurance", "Equipment", "Accumulated Depreciation", 
        "Accounts Payable", "Notes Payable", "Salaries Payable", 
        "Common Stock", "Dividends", 
        "Service Revenue", "Interest Revenue", 
        "Depreciation Expense", "Interest Expense", "Miscellaneous Expense", 
        "Rent Expense", "Salaries Expense", "Supplies Expense", 
        "Utilities Expense", "Advertising Expense", "Insurance Expense"
    ]

    def __init__(self, student_id: str, trimester_code: str = "T1_2026"):
        self.student_id = student_id
        self.trimester_code = trimester_code
        self.seed = get_seed_from_id(student_id, trimester_code)
        self.rng = random.Random(self.seed)
        
        self.journal_raw = []
        self.journal = []
        self.trial_balance = {}
        self.transactions_text = []

        # State storage for chained dependencies
        self.context = {}

        self._build_pool()

    def _add_entry(self, account: str, amount: float, entry_type: str):
        if account not in self.trial_balance:
            self.trial_balance[account] = 0.0
            
        if entry_type == 'Debit':
            self.trial_balance[account] += amount
        elif entry_type == 'Credit':
            self.trial_balance[account] -= amount
        else:
            raise ValueError("Type must be Debit or Credit")

    def _record_transaction(self, day: int, description: str, debits: list, credits: list, is_initial: bool = False):
        self.journal_raw.append({
            'day': day,
            'is_initial': is_initial,
            'description': description,
            'debits': [(acc, round(amt, 2)) for acc, amt in debits],
            'credits': [(acc, round(amt, 2)) for acc, amt in credits]
        })

    def _build_pool(self):
        """Constructs the mapping of templates."""
        self.templates = {}

        # --------------------
        # TVM PAIRS (10 templates)
        # --------------------
        loans = [(1, 3, 0.05), (2, 5, 0.06), (3, 4, 0.07)]
        for i, years, rate in loans:
            def op_loan(ctx, i=i, y=years, r=rate):
                amt = self.rng.randint(20, 80) * 1000
                ctx[f'loan_{i}_amt'] = amt
                ctx[f'loan_{i}_y'] = y
                ctx[f'loan_{i}_r'] = r
                self._record_transaction(1,
                    f"Took out a ${amt:,} bank loan on the first day of the month. Amortized over {y} years at {r*100:.1f}% annually.",
                    [('Cash', amt)], [('Notes Payable', amt)]
                )
            
            def adj_loan(ctx, i=i):
                amt = ctx[f'loan_{i}_amt']
                r = ctx[f'loan_{i}_r'] / 12
                months = ctx[f'loan_{i}_y'] * 12
                pmt = round(float(-npf.pmt(r, months, amt)), 2)
                interest = round(amt * r, 2)
                principal = round(pmt - interest, 2)
                self._record_transaction(31,
                    f"Made the first monthly loan payment (Loan {i}). Calculate the correct PMT and interest accrual.",
                    [('Notes Payable', principal), ('Interest Expense', interest)], [('Cash', pmt)]
                )
            self.templates[f'OP_LOAN_{i}'] = {'cat': 'TVM_OP', 'func': op_loan}
            self.templates[f'ADJ_LOAN_{i}'] = {'cat': 'TVM_ADJ', 'dep': f'OP_LOAN_{i}', 'func': adj_loan}

        stis = [(1, 0.04), (2, 0.05)]
        for i, rate in stis:
            def op_sti(ctx, i=i, r=rate):
                amt = self.rng.randint(10, 30) * 1000
                ctx[f'sti_{i}_amt'] = amt
                ctx[f'sti_{i}_r'] = r
                day = self.rng.randint(2, 10)
                self._record_transaction(day, f"Invested ${amt:,} cash in a short-term bond.", [('Short-Term Investments', amt)], [('Cash', amt)])
                
            def adj_sti(ctx, i=i):
                amt = ctx[f'sti_{i}_amt']
                r = ctx[f'sti_{i}_r']
                int_rev = round(amt * r / 12, 2)
                self._record_transaction(31, f"Accrued 1 month of interest revenue on the short-term bond ({r*100:.1f}% annual).", [('Interest Receivable', int_rev)], [('Interest Revenue', int_rev)])
                
            self.templates[f'OP_STI_{i}'] = {'cat': 'TVM_OP', 'func': op_sti}
            self.templates[f'ADJ_STI_{i}'] = {'cat': 'TVM_ADJ', 'dep': f'OP_STI_{i}', 'func': adj_sti}

        # --------------------
        # ADJUSTING PAIRS (20 templates)
        # --------------------
        # Equipment / Depreciation
        equipment_ids = ["Server Unit A", "Office Suite 101", "Delivery Van", "3D Printer X", "Conference Table C", "Mainframe B"]
        for i in range(1, 4):
            def op_eq(ctx, i=i):
                cost = self.rng.randint(15, 60) * 1000
                asset_id = self.rng.choice(equipment_ids)
                ctx[f'eq_{i}_cost'] = cost
                ctx[f'eq_{i}_id'] = asset_id
                # Equipment purchases MUST be Jan 1
                self._record_transaction(1, f"Purchased {asset_id} for ${cost:,} cash.", [('Equipment', cost)], [('Cash', cost)])
            def adj_eq(ctx, i=i):
                cost = ctx[f'eq_{i}_cost']
                asset_id = ctx[f'eq_{i}_id']
                depr = round(cost / (5 * 12), 2)
                self._record_transaction(31, f"Record depreciation on {asset_id} (5 yrs, straight-line, $0 salvage).", [('Depreciation Expense', depr)], [('Accumulated Depreciation', depr)])
            self.templates[f'OP_EQ_{i}'] = {'cat': 'OP', 'func': op_eq}
            self.templates[f'ADJ_EQ_{i}'] = {'cat': 'ADJ', 'dep': f'OP_EQ_{i}', 'func': adj_eq}

        # Prepaid Rent
        for i, months in [(1, 6), (2, 12), (3, 3)]:
            def op_rent(ctx, i=i, m=months):
                monthly = self.rng.randint(10, 30) * 100
                total = monthly * m
                ctx[f'rent_{i}_monthly'] = monthly
                self._record_transaction(1, f"Paid {m} months rent in advance: ${total:,}.", [('Prepaid Rent', total)], [('Cash', total)])
            def adj_rent(ctx, i=i):
                monthly = ctx[f'rent_{i}_monthly']
                self._record_transaction(31, f"Record 1 month of expired rent (contract {i}).", [('Rent Expense', monthly)], [('Prepaid Rent', monthly)])
            self.templates[f'OP_RENT_{i}'] = {'cat': 'OP', 'func': op_rent}
            self.templates[f'ADJ_RENT_{i}'] = {'cat': 'ADJ', 'dep': f'OP_RENT_{i}', 'func': adj_rent}

        # Prepaid Insurance
        for i, months in [(1, 6), (2, 12)]:
            def op_ins(ctx, i=i, m=months):
                monthly = self.rng.randint(10, 30) * 10
                total = monthly * m
                ctx[f'ins_{i}_monthly'] = monthly
                self._record_transaction(1, f"Paid {m} months business insurance in advance: ${total:,}.", [('Prepaid Insurance', total)], [('Cash', total)])
            def adj_ins(ctx, i=i):
                monthly = ctx[f'ins_{i}_monthly']
                self._record_transaction(31, f"Record 1 month of expired insurance (policy {i}).", [('Insurance Expense', monthly)], [('Prepaid Insurance', monthly)])
            self.templates[f'OP_INS_{i}'] = {'cat': 'OP', 'func': op_ins}
            self.templates[f'ADJ_INS_{i}'] = {'cat': 'ADJ', 'dep': f'OP_INS_{i}', 'func': adj_ins}

        # Supplies
        for i in range(1, 3):
            def op_sup(ctx, i=i):
                cost = self.rng.randint(5, 25) * 100
                ctx[f'sup_{i}_cost'] = cost
                day = self.rng.randint(2, 15)
                self._record_transaction(day, f"Purchased batch {i} of supplies on account for ${cost:,}.", [('Supplies', cost)], [('Accounts Payable', cost)])
            def adj_sup(ctx, i=i):
                cost = ctx[f'sup_{i}_cost']
                used = round(cost * self.rng.uniform(0.3, 0.7), 2)
                on_hand = cost - used
                self._record_transaction(31, f"Batch {i} physical count shows ${on_hand:,} supplies on hand. Record adjusting entry.", [('Supplies Expense', used)], [('Supplies', used)])
            self.templates[f'OP_SUP_{i}'] = {'cat': 'OP', 'func': op_sup}
            self.templates[f'ADJ_SUP_{i}'] = {'cat': 'ADJ', 'dep': f'OP_SUP_{i}', 'func': adj_sup}

        # Accrued Salaries
        for i in range(1, 3):
            def op_sal(ctx, i=i):
                 amt = self.rng.randint(20, 50) * 100
                 ctx[f'sal_{i}_amt'] = amt
                 day = self.rng.randint(10, 20)
                 self._record_transaction(day, f"Paid mid-month regular salaries of ${amt:,} to staff group {i}.", [('Salaries Expense', amt)], [('Cash', amt)])
            def adj_sal(ctx, i=i):
                 amt = ctx[f'sal_{i}_amt']
                 accrued = round(amt * self.rng.uniform(0.3, 0.6), 2)
                 self._record_transaction(31, f"Staff group {i} earned ${accrued:,} in final days of month not yet paid.", [('Salaries Expense', accrued)], [('Salaries Payable', accrued)])
            self.templates[f'OP_SAL_{i}'] = {'cat': 'OP', 'func': op_sal}
            self.templates[f'ADJ_SAL_{i}'] = {'cat': 'ADJ', 'dep': f'OP_SAL_{i}', 'func': adj_sal}


        # --------------------
        # INDEPENDENT OPERATIONAL
        # --------------------
        # Service Revenue Cash
        for i in range(5):
            def rev_cash(ctx, idx=i):
                amt = self.rng.randint(50, 150) * 100
                day = self.rng.randint(2, 25)
                self._record_transaction(day, f"Performed ad-hoc service {idx} for customers and received ${amt:,} cash.", [('Cash', amt)], [('Service Revenue', amt)])
            self.templates[f'IND_REV_CASH_{i}'] = {'cat': 'IND_OP', 'func': rev_cash, 'count': 1}

        # Service Revenue Credit & AR Collection (Tied chronologically)
        for i in range(5):
            def rev_cred_pair(ctx, idx=i):
                amt = self.rng.randint(60, 200) * 100
                day_rev = self.rng.randint(2, 20)
                client = self.rng.choice(["Alpha Corp", "Beta LLC", "Gamma Inc", "Delta Co", "Omega Systems"])
                
                # Must collect at least 5 days later
                day_col = self.rng.randint(day_rev + 5, 29)
                
                self._record_transaction(day_rev, f"Performed project {idx} for {client} on account for ${amt:,}.", [('Accounts Receivable', amt)], [('Service Revenue', amt)])
                self._record_transaction(day_col, f"Received ${amt:,} cash from {client} in full settlement of their account.", [('Cash', amt)], [('Accounts Receivable', amt)])
            
            self.templates[f'IND_REV_CRED_PAIR_{i}'] = {'cat': 'IND_OP', 'func': rev_cred_pair, 'count': 2}

        # Pay Accounts Payable
        for i in range(3):
            def pay_ap(ctx):
                amt = self.rng.randint(2, 8) * 100
                day = self.rng.randint(15, 25)
                self._record_transaction(day, f"Paid ${amt:,} cash towards general accounts payable.", [('Accounts Payable', amt)], [('Cash', amt)])
            self.templates[f'IND_PAY_AP_{i}'] = {'cat': 'IND_OP', 'func': pay_ap, 'count': 1}

        # Utilities
        for i in range(3):
            def util(ctx, idx=i):
                amt = self.rng.randint(2, 6) * 100
                day = self.rng.randint(2, 25)
                self._record_transaction(day, f"Paid utility bill region {idx} for ${amt:,} cash.", [('Utilities Expense', amt)], [('Cash', amt)])
            self.templates[f'IND_UTIL_{i}'] = {'cat': 'IND_OP', 'func': util, 'count': 1}

        # Advertising
        for i in range(2):
            def adv_exp(ctx, idx=i):
                amt = self.rng.randint(2, 10) * 100
                day = self.rng.randint(2, 25)
                desc = self.rng.choice(["Paid for Google Ads campaign", "Printed promotional brochures"])
                self._record_transaction(day, f"{desc} costing ${amt:,}.", [('Advertising Expense', amt)], [('Cash', amt)])
            self.templates[f'IND_ADV_{i}'] = {'cat': 'IND_OP', 'func': adv_exp, 'count': 1}

        # Misc & Dividends
        for i in range(2):
            def misc(ctx):
                amt = self.rng.randint(1, 4) * 100
                day = self.rng.randint(2, 25)
                self._record_transaction(day, f"Paid ${amt:,} for miscellaneous items.", [('Miscellaneous Expense', amt)], [('Cash', amt)])
            self.templates[f'IND_MISC_{i}'] = {'cat': 'IND_OP', 'func': misc, 'count': 1}

        for i in range(2):
            def div(ctx):
                amt = self.rng.randint(5, 15) * 100
                day = self.rng.randint(15, 25)
                self._record_transaction(day, f"Declared and paid ${amt:,} in cash dividends.", [('Dividends', amt)], [('Cash', amt)])
            self.templates[f'IND_DIV_{i}'] = {'cat': 'IND_OP', 'func': div, 'count': 1}

    def generate(self, exact_transactions: int = 19):
        """Dynamic selection algorithm to hit exactly 20 bounds (inclusive of initial)."""
        current_op_count = 0

        # 1. Pick TVM (1 ADJ, triggers 1 OP) = 2 transactions
        tvm_adjs = [k for k, v in self.templates.items() if v['cat'] == 'TVM_ADJ']
        chosen_tvm = self.rng.choice(tvm_adjs)
        tvm_obj = self.templates[chosen_tvm]
        
        self.templates[tvm_obj['dep']]['func'](self.context)
        tvm_obj['func'](self.context)
        current_op_count += 2
        
        # 2. Pick Adjusting (target_adj count)
        target_adj = 4 # Gives 8 transactions
        all_adjs = [k for k, v in self.templates.items() if v['cat'] == 'ADJ']
        chosen_adjs = self.rng.sample(all_adjs, k=target_adj)
        
        for adj in chosen_adjs:
            adj_obj = self.templates[adj]
            self.templates[adj_obj['dep']]['func'](self.context)
            adj_obj['func'](self.context)
            current_op_count += 2

        # 3. Fill remaining Operational up to exact_transactions
        remaining_ops = exact_transactions - current_op_count
        all_ind_ops = [k for k, v in self.templates.items() if v['cat'] == 'IND_OP']
        self.rng.shuffle(all_ind_ops)
        
        for io in all_ind_ops:
            if remaining_ops <= 0:
                break
            io_obj = self.templates[io]
            io_obj['func'](self.context)
            # count could be 1 or 2 (for paired events)
            remaining_ops -= io_obj.get('count', 1)

        # 4. Calculate proper Investment to prevent negative Cash
        # Determine maximum cash credited
        total_cash_out = sum(
            amt for entry in self.journal_raw 
                for acc, amt in entry['credits'] if acc == 'Cash'
        )
        
        # 2.5x the max possible 'Cash Out' sum
        investment = round((total_cash_out * 2.5) / 1000) * 1000
        if investment < 50000:
            investment = 50000

        self._record_transaction(
            1, 
            f"Started business with ${investment:,} investment in exchange for Common Stock.",
            [('Cash', investment)], [('Common Stock', investment)],
            is_initial=True
        )

        # 5. Sort Sequence Chronologically
        # The is_initial flag ensures Transaction 0 always comes first.
        def sort_key(entry):
            return (entry['day'], 0 if entry['is_initial'] else 1)
            
        self.journal_raw.sort(key=sort_key)
        
        # 6. Apply to Trial Balance and final Text
        for i, entry in enumerate(self.journal_raw):
            day_str = f"Jan {entry['day']}"
            desc = entry['description']
            
            # Format text explicitly with Day and start numbering at 0
            self.transactions_text.append(f"{i}. [{day_str}] {desc}")
            
            for acc, amt in entry['debits']:
                assert acc in self.STANDARD_COA, f"CRITICAL: '{acc}' not in STANDARD_COA!"
                self.journal.append({'date': day_str, 'description': desc, 'account': acc, 'debit': amt, 'credit': 0.0})
                self._add_entry(acc, amt, 'Debit')
                
            for acc, amt in entry['credits']:
                assert acc in self.STANDARD_COA, f"CRITICAL: '{acc}' not in STANDARD_COA!"
                self.journal.append({'date': day_str, 'description': desc, 'account': acc, 'debit': 0.0, 'credit': amt})
                self._add_entry(acc, amt, 'Credit')

    def get_ground_truth(self) -> pd.DataFrame:
        df = pd.DataFrame(list(self.trial_balance.items()), columns=['Account', 'Balance'])
        df['Debit'] = df['Balance'].apply(lambda x: x if x > 0 else 0)
        df['Credit'] = df['Balance'].apply(lambda x: -x if x < 0 else 0)
        df = df.drop(columns=['Balance'])
        df = df[(df['Debit'] > 0) | (df['Credit'] > 0)]
        return df.sort_values(by='Account').reset_index(drop=True)

if __name__ == "__main__":
    student_id = "SIT12345"
    generator = AccountancyGenerator(student_id)
    generator.generate(exact_transactions=19) # Total will be 20 (+1 Initial)
    
    print(f"--- Generated length: {len(generator.transactions_text)} ---")
    for t in generator.transactions_text:
        print(t)
        
    tb = generator.get_ground_truth()
    print("\n--- Trial Balance ---")
    print(tb)
    print(f"Total Debits: {tb['Debit'].sum():.2f}")
