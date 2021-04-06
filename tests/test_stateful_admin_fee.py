from .stateful_base import StatefulBase
from brownie.test import strategy

MAX_SAMPLES = 20
STEP_COUNT = 20
NO_CHANGE = 2**256-1


class StatefulAdmin(StatefulBase):
    exchange_amount_in = strategy('uint256', min_value=10**17, max_value=10**5 * 10**18)
    vol = 0

    def setup(self):
        super().setup(user_id=1)
        admin = self.accounts[0]
        self.swap.commit_new_parameters(
            NO_CHANGE,
            NO_CHANGE,
            5 * 10**9,  # admin fee
            NO_CHANGE,
            NO_CHANGE,
            NO_CHANGE,
            NO_CHANGE,
            {'from': admin})
        self.chain.sleep(3 * 86400 + 1)
        self.swap.apply_new_parameters({'from': admin})
        assert self.swap.admin_fee() == 5 * 10**9
        self.mid_fee = self.swap.mid_fee()
        self.out_fee = self.swap.out_fee()
        self.admin_fee = 5 * 10**9

    def rule_exchange(self, exchange_amount_in, exchange_i, exchange_j, user):
        if exchange_i > 0:
            exchange_amount_in_converted = exchange_amount_in * 10**18 // self.swap.price_oracle(exchange_i - 1)
        else:
            exchange_amount_in_converted = exchange_amount_in
        if super().rule_exchange(exchange_amount_in_converted, exchange_i, exchange_j, user):
            self.vol += exchange_amount_in * self.swap.virtual_price() // 10**18

    def rule_claim_admin_fees(self):
        balance = self.token.balanceOf(self.accounts[0])
        self.swap.claim_admin_fees()
        balance = self.token.balanceOf(self.accounts[0]) - balance
        if balance > 0:
            self.xcp_profit = self.xcp_profit * self.total_supply // (self.total_supply + balance)
            self.total_supply += balance
            assert self.vol > 0

            prices = [10**18] + [self.swap.price_scale(i) for i in range(2)]

            measured_profit = self.token.balanceOf(self.accounts[0]) * sum(self.swap.balances(i) * prices[i] // 10**18 for i in range(3)) // self.total_supply
            min_profit = self.vol * self.mid_fee // 10**10 * self.admin_fee // 10**10 // 2
            max_profit = self.vol * self.out_fee // 10**10 * self.admin_fee // 10**10 // 2
            # USD prices change a little bit, so we accommodate for that here
            assert measured_profit >= min_profit * 0.9
            assert measured_profit <= max_profit * 1.1


def test_admin(crypto_swap, token, chain, accounts, coins, state_machine):
    state_machine(StatefulAdmin, chain, accounts, coins, crypto_swap, token,
                  settings={'max_examples': MAX_SAMPLES, 'stateful_step_count': STEP_COUNT})
