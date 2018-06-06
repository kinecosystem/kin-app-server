import arrow

from kinappserver import db
from kinappserver.utils import InternalError


class BlackhawkCard(db.Model):
    """the BlackhawkCard class represent a single card from the OmniCode API.

    cards are created by orders. There may be multiple cards in each order.
    """
    card_id = db.Column(db.String(40), primary_key=True, nullable=False)
    order_id = db.Column(db.String(40), nullable=False)
    processed = db.Column(db.Boolean, unique=False, default=False)
    merchant_code = db.Column(db.String(40))
    denomination = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return '<card_id: %s, order_id: %s, merchant_code: %s, denomination: %s, processed: %s, updated_at: %s>' % (self.card_id, self.order_id, self.merchant_code, self.denomination, self.processed, self.updated_at)


def create_bh_card(card_id, order_id, merchant_code, denomination):
    """creates a new instance of BlackhawkCard"""
    try:

        card = BlackhawkCard()
        card.card_id = card_id
        card.order_id = order_id
        card.merchant_code = merchant_code
        card.denomination = denomination

        db.session.add(card)
        db.session.commit()
    except Exception as e:
        print('failed to create a new blackhawk card with id: %s' % card_id)
        print(e)
        raise InternalError('failed to create a new blackhawk card')
    else:
        return True


def list_all_bh_cards():
    """returns a dict of all the cards"""
    response = {}
    cards = BlackhawkCard.query.order_by(BlackhawkCard.updated_at).all()
    for card in cards:
        response[card.card_id] = {'order_id': card.order_id, 'processed': card.processed, 'card_id': card.card_id}
    return response


def set_processed_orders(card_ids):
    """sets the processed flag on the cards with the the given ids"""
    for card_id in card_ids:
        # TODO switch to _in
        card = BlackhawkCard.query.filter_by(card_id=card_id).first()
        if not card:
            print('could not retrieve card id %s in db' % card_id)
            return None
        card.processed = True
        db.session.add(card)
    db.session.commit()


def list_unprocessed_orders():
    """returns a dict of all the unprocessed orders with their respective card id"""
    orders = {}
    cards = BlackhawkCard.query.order_by(BlackhawkCard.updated_at).filter(BlackhawkCard.processed == False).all()
    for card in cards:
        if card.order_id in orders:
            orders[card.order_id] = orders[card.order_id].append(card.card_id)
        else:
            orders[card.order_id] = [card.card_id]
    return orders
