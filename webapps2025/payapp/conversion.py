from decimal import Decimal

def convert_currency(amount, from_currency, to_currency):
    print(f"Calling REST API for: {amount} {from_currency} to {to_currency}")
    rates = {
        'USD': Decimal('1.0'),
        'GBP': Decimal('0.77'),
        'EUR': Decimal('0.9'),
    }

    if from_currency not in rates or to_currency not in rates:
        return None

    amount = Decimal(str(amount))
    base_amount = amount / rates[from_currency]
    converted_amount = base_amount * rates[to_currency]
    return round(converted_amount, 2)
