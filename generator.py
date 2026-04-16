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
    def __init__(self, student_id: str, trimester_code: str = "T1_2026"):
        self.student_id = student_id
        self.trimester_code = trimester_code
        self.seed = get_seed_from_id(student_id, trimester_code)
        self.rng = random.Random(self.seed)
        
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

    def _record_transaction(self, description: str, debits: list, credits: list):
        self.transactions_text.append(description)
        for account, amount in debits:
            amount = round(amount, 2)
            self.journal.append({'description': description, 'account': account, 'debit': amount, 'credit': 0.0})
            self._add_entry(account, amount, 'Debit')
            
        for account, amount in credits:
            amount = round(amount, 2)
            self.journal.append({'description': description, 'account': account, 'debit': 0.0, 'credit': amount})
            self._add_entry(account, amount, 'Credit')

    def _build_pool(self):
        """Constructs the mapping of 50+ templates."""
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
                self._record_transaction(
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
                self._record_transaction(
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
                self._record_transaction(f"Invested ${amt:,} cash in a short-term bond.", [('Short-Term Investments', amt)], [('Cash', amt)])
                
            def adj_sti(ctx, i=i):
                amt = ctx[f'sti_{i}_amt']
                r = ctx[f'sti_{i}_r']
                int_rev = round(amt * r / 12, 2)
                self._record_transaction(f"Accrued 1 month of interest revenue on the short-term bond ({r*100:.1f}% annual).", [('Interest Receivable', int_rev)], [('Interest Revenue', int_rev)])
                
            self.templates[f'OP_STI_{i}'] = {'cat': 'TVM_OP', 'func': op_sti}
            self.templates[f'ADJ_STI_{i}'] = {'cat': 'TVM_ADJ', 'dep': f'OP_STI_{i}', 'func': adj_sti}

        # --------------------
        # ADJUSTING PAIRS (20 templates)
        # --------------------
        # Equipment / Depreciation
        for i in range(1, 4):
            def op_eq(ctx, i=i):
                cost = self.rng.randint(15, 60) * 1000
                ctx[f'eq_{i}_cost'] = cost
                self._record_transaction(f"Purchased equipment style {i} for ${cost:,} cash.", [('Equipment', cost)], [('Cash', cost)])
            def adj_eq(ctx, i=i):
                cost = ctx[f'eq_{i}_cost']
                depr = round(cost / (5 * 12), 2)
                self._record_transaction(f"Record depreciation on equipment style {i} (5 yrs, straight-line, $0 salvage).", [('Depreciation Expense', depr)], [('Accumulated Depreciation', depr)])
            self.templates[f'OP_EQ_{i}'] = {'cat': 'OP', 'func': op_eq}
            self.templates[f'ADJ_EQ_{i}'] = {'cat': 'ADJ', 'dep': f'OP_EQ_{i}', 'func': adj_eq}

        # Prepaid Rent
        for i, months in [(1, 6), (2, 12), (3, 3)]:
            def op_rent(ctx, i=i, m=months):
                monthly = self.rng.randint(10, 30) * 100
                total = monthly * m
                ctx[f'rent_{i}_monthly'] = monthly
                self._record_transaction(f"Paid {m} months rent in advance: ${total:,}.", [('Prepaid Rent', total)], [('Cash', total)])
            def adj_rent(ctx, i=i):
                monthly = ctx[f'rent_{i}_monthly']
                self._record_transaction(f"Record 1 month of expired rent (contract {i}).", [('Rent Expense', monthly)], [('Prepaid Rent', monthly)])
            self.templates[f'OP_RENT_{i}'] = {'cat': 'OP', 'func': op_rent}
            self.templates[f'ADJ_RENT_{i}'] = {'cat': 'ADJ', 'dep': f'OP_RENT_{i}', 'func': adj_rent}

        # Supplies
        for i in range(1, 3):
            def op_sup(ctx, i=i):
                cost = self.rng.randint(5, 25) * 100
                ctx[f'sup_{i}_cost'] = cost
                self._record_transaction(f"Purchased batch {i} of supplies on account for ${cost:,}.", [('Supplies', cost)], [('Accounts Payable', cost)])
            def adj_sup(ctx, i=i):
                cost = ctx[f'sup_{i}_cost']
                used = round(cost * self.rng.uniform(0.3, 0.7), 2)
                on_hand = cost - used
                self._record_transaction(f"Batch {i} physical count shows ${on_hand:,} supplies on hand. Record adjusting entry.", [('Supplies Expense', used)], [('Supplies', used)])
            self.templates[f'OP_SUP_{i}'] = {'cat': 'OP', 'func': op_sup}
            self.templates[f'ADJ_SUP_{i}'] = {'cat': 'ADJ', 'dep': f'OP_SUP_{i}', 'func': adj_sup}

        # Accrued Salaries
        for i in range(1, 3):
            def op_sal(ctx, i=i):
                 # Dummy op just to register there are employees
                 amt = self.rng.randint(20, 50) * 100
                 ctx[f'sal_{i}_amt'] = amt
                 self._record_transaction(f"Paid mid-month regular salaries of ${amt:,} to staff group {i}.", [('Salaries Expense', amt)], [('Cash', amt)])
            def adj_sal(ctx, i=i):
                 amt = ctx[f'sal_{i}_amt']
                 accrued = round(amt * self.rng.uniform(0.3, 0.6), 2)
                 self._record_transaction(f"Staff group {i} earned ${accrued:,} in final days of month not yet paid.", [('Salaries Expense', accrued)], [('Salaries Payable', accrued)])
            self.templates[f'OP_SAL_{i}'] = {'cat': 'OP', 'func': op_sal}
            self.templates[f'ADJ_SAL_{i}'] = {'cat': 'ADJ', 'dep': f'OP_SAL_{i}', 'func': adj_sal}


        # --------------------
        # INDEPENDENT OPERATIONAL (20+ templates)
        # --------------------
        # Service Revenue Cash
        for i in range(5):
            def rev_cash(ctx, idx=i):
                amt = self.rng.randint(50, 150) * 100
                self._record_transaction(f"Performed ad-hoc service {idx} for customers and received ${amt:,} cash.", [('Cash', amt)], [('Service Revenue', amt)])
            self.templates[f'IND_REV_CASH_{i}'] = {'cat': 'IND_OP', 'func': rev_cash}

        # Service Revenue Credit
        for i in range(5):
            def rev_cred(ctx, idx=i):
                amt = self.rng.randint(60, 200) * 100
                ctx[f'ar_{idx}'] = amt
                self._record_transaction(f"Performed project {idx} on account for ${amt:,}.", [('Accounts Receivable', amt)], [('Service Revenue', amt)])
            self.templates[f'IND_REV_CRED_{i}'] = {'cat': 'IND_OP', 'func': rev_cred}

        # Pay Accounts Payable
        for i in range(3):
            def pay_ap(ctx):
                amt = self.rng.randint(2, 8) * 100
                self._record_transaction(f"Paid ${amt:,} cash towards general accounts payable.", [('Accounts Payable', amt)], [('Cash', amt)])
            self.templates[f'IND_PAY_AP_{i}'] = {'cat': 'IND_OP', 'func': pay_ap}

        # Receive Accounts Receivable
        for i in range(3):
            def rec_ar(ctx):
                amt = self.rng.randint(10, 40) * 100
                self._record_transaction(f"Received ${amt:,} cash from various customers on account.", [('Cash', amt)], [('Accounts Receivable', amt)])
            self.templates[f'IND_REC_AR_{i}'] = {'cat': 'IND_OP', 'func': rec_ar}

        # Utilities
        for i in range(3):
            def util(ctx, idx=i):
                amt = self.rng.randint(2, 6) * 100
                self._record_transaction(f"Paid utility bill region {idx} for ${amt:,} cash.", [('Utilities Expense', amt)], [('Cash', amt)])
            self.templates[f'IND_UTIL_{i}'] = {'cat': 'IND_OP', 'func': util}

        # Misc & Dividends
        for i in range(2):
            def misc(ctx):
                amt = self.rng.randint(1, 4) * 100
                self._record_transaction(f"Paid ${amt:,} for miscellaneous items.", [('Miscellaneous Expense', amt)], [('Cash', amt)])
            self.templates[f'IND_MISC_{i}'] = {'cat': 'IND_OP', 'func': misc}

        for i in range(2):
            def div(ctx):
                amt = self.rng.randint(5, 15) * 100
                self._record_transaction(f"Declared and paid ${amt:,} in cash dividends.", [('Dividends', amt)], [('Cash', amt)])
            self.templates[f'IND_DIV_{i}'] = {'cat': 'IND_OP', 'func': div}

    def generate(self):
        """Dynamic selection algorithm to hit exactly 20-24 bounds."""
        target_op = self.rng.randint(14, 16)
        target_adj = self.rng.randint(4, 6)
        target_tvm = 2 # 1 OP, 1 ADJ

        # 1. Always inject Initial Investment manually (No template, guarantees Cash)
        investment = self.rng.randint(200, 500) * 1000
        self._record_transaction(
            f"Started business with ${investment:,} investment in exchange for Common Stock.",
            [('Cash', investment)], [('Common Stock', investment)]
        )
        current_op = 1 # Initial tracking count

        selected_events = []
        op_event_funcs = []
        adj_event_funcs = []

        # 2. Pick TVM (1 ADJ, triggers 1 OP)
        tvm_adjs = [k for k, v in self.templates.items() if v['cat'] == 'TVM_ADJ']
        chosen_tvm = self.rng.choice(tvm_adjs)
        tvm_obj = self.templates[chosen_tvm]
        
        # Add dependency to OP sequence
        op_event_funcs.append(self.templates[tvm_obj['dep']]['func'])
        current_op += 1
        
        # Add ADJ to ADJ sequence
        adj_event_funcs.append(tvm_obj['func'])

        # 3. Pick Adjusting (target_adj count)
        all_adjs = [k for k, v in self.templates.items() if v['cat'] == 'ADJ']
        chosen_adjs = self.rng.sample(all_adjs, k=target_adj)
        
        for adj in chosen_adjs:
            adj_obj = self.templates[adj]
            op_event_funcs.append(self.templates[adj_obj['dep']]['func'])
            current_op += 1
            adj_event_funcs.append(adj_obj['func'])

        # 4. Fill remaining Operational up to target_op
        remaining_ops = target_op - current_op
        all_ind_ops = [k for k, v in self.templates.items() if v['cat'] == 'IND_OP']
        
        if remaining_ops > 0:
            chosen_ind_ops = self.rng.sample(all_ind_ops, k=remaining_ops)
            for io in chosen_ind_ops:
                op_event_funcs.append(self.templates[io]['func'])

        # 5. Execute OP Sequence (Randomized order)
        self.rng.shuffle(op_event_funcs)
        for func in op_event_funcs:
            func(self.context)

        # 6. Execute ADJ Sequence (Usually at end of month)
        # Shuffle internally to mix TVM Adj and Regular Adj
        self.rng.shuffle(adj_event_funcs)
        for func in adj_event_funcs:
            func(self.context)
            
        # Ensure sequential numbering
        new_text = []
        for i, text in enumerate(self.transactions_text):
            new_text.append(f"{i+1}. {text}")
        self.transactions_text = new_text

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
    generator.generate()
    
    print(f"--- Generated length: {len(generator.transactions_text)} ---")
    tb = generator.get_ground_truth()
    print(tb)
    print(f"Debits: {tb['Debit'].sum():.2f}")
