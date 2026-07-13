import uuid


class UuidGen:
    # UUID4 = 122 random bits. Generated app-side (we need the processor_key in hand
    # BEFORE the charge, so a re-drive can repeat it). Collision is astronomically
    # unlikely; the DB UNIQUE constraint is the safety net if the impossible happens.
    def new_payment_id(self) -> str:
        return "pay_" + uuid.uuid4().hex

    def new_processor_key(self) -> str:
        return "pk_" + uuid.uuid4().hex
