from .book_side import BookSide, HeapBookSide
from .types import Order, OrderType, Side, Trade


class OrderBook:
    def __init__(self, book_side_cls: type[BookSide] = HeapBookSide) -> None:
        self.ask_book: BookSide = book_side_cls(Side.SELL)
        self.bid_book: BookSide = book_side_cls(Side.BUY)
        self.order_diary: dict[int, Order] = {}
        self.counter = 0
        self.trade_id_counter = 0

    def _validate_new_order(self, order_id: int, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if order_id in self.order_diary:
            raise ValueError(f"duplicate order id: {order_id}")

    def _match(
        self,
        taker_id: int,
        side: Side,
        quantity: int,
        limit_price: int | None,
        timestamp: int,
    ) -> tuple[list[Trade], int]:
        trades: list[Trade] = []
        opposite_side = self.ask_book if side == Side.BUY else self.bid_book
        remaining = quantity

        while remaining > 0:
            best_price = opposite_side.get_best_price()
            if best_price is None:
                break
            if limit_price is not None:
                if side == Side.BUY and limit_price < best_price:
                    break
                if side == Side.SELL and limit_price > best_price:
                    break

            matched_order = opposite_side.peek_best_order()
            if matched_order is None or matched_order.is_cancelled:
                opposite_side.pop_best_order()
                continue

            assert matched_order.price is not None

            fill_quantity = min(remaining, matched_order.quantity)
            remaining -= fill_quantity

            self.trade_id_counter += 1
            trades.append(Trade(
                trade_id=self.trade_id_counter,
                maker_id=matched_order.order_id,
                taker_id=taker_id,
                price=matched_order.price,
                quantity=fill_quantity,
                timestamp=timestamp,
            ))

            if fill_quantity == matched_order.quantity:
                opposite_side.pop_best_order()
                self.order_diary.pop(matched_order.order_id, None)
            else:
                matched_order.quantity -= fill_quantity
                opposite_side.reduce_volume(matched_order.price, fill_quantity)

        return trades, remaining

    def process_limit_order(
        self, order_id: int, price: int, quantity: int, side: Side
    ) -> list[Trade]:
        self._validate_new_order(order_id, quantity)
        self.counter += 1
        current_time = self.counter

        trades, remaining_quantity = self._match(order_id, side, quantity, price, current_time)

        if remaining_quantity > 0:
            own_side = self.bid_book if side == Side.BUY else self.ask_book
            new_order = Order(
                order_id=order_id,
                side=side,
                order_type=OrderType.LIMIT,
                price=price,
                quantity=remaining_quantity,
                timestamp=current_time,
            )
            self.order_diary[order_id] = new_order
            own_side.add_order(new_order)

        return trades

    def process_market_order(self, order_id: int, quantity: int, side: Side) -> list[Trade]:
        self._validate_new_order(order_id, quantity)
        self.counter += 1
        trades, _ = self._match(order_id, side, quantity, None, self.counter)
        return trades

    def cancel_order(self, order_id: int) -> bool:
        if order_id not in self.order_diary:
            return False

        order = self.order_diary[order_id]
        order.is_cancelled = True
        own_side = self.bid_book if order.side == Side.BUY else self.ask_book
        assert order.price is not None
        own_side.reduce_volume(order.price, order.quantity)

        del self.order_diary[order_id]
        return True

    def modify_order(self, order_id: int, new_price: int, new_quantity: int) -> list[Trade]:
        if order_id not in self.order_diary:
            return []
        if new_quantity <= 0:
            raise ValueError("quantity must be positive")

        order = self.order_diary[order_id]
        assert order.price is not None

        if new_price == order.price and new_quantity <= order.quantity:
            own_side = self.bid_book if order.side == Side.BUY else self.ask_book
            own_side.reduce_volume(order.price, order.quantity - new_quantity)
            order.quantity = new_quantity
            return []

        side = order.side
        self.cancel_order(order_id)
        return self.process_limit_order(order_id, new_price, new_quantity, side)

    def best_bid(self) -> tuple[int, int] | None:
        levels = self.bid_book.get_top_levels(1)
        return levels[0] if levels else None

    def best_ask(self) -> tuple[int, int] | None:
        levels = self.ask_book.get_top_levels(1)
        return levels[0] if levels else None

    def spread(self) -> int | None:
        bid = self.bid_book.get_best_price()
        ask = self.ask_book.get_best_price()
        if bid is None or ask is None:
            return None
        return ask - bid

    def depth(self, n: int) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        return self.bid_book.get_top_levels(n), self.ask_book.get_top_levels(n)
