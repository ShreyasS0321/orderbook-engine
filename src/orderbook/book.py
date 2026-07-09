from .book_side import HeapBookSide
from .types import Order, OrderType, Side, Trade


class OrderBook:
    
    def __init__(self)->None:
        self.ask_book : HeapBookSide=HeapBookSide(Side.SELL)
        self.bid_book: HeapBookSide =HeapBookSide(Side.BUY)
        self.order_diary: dict[int,Order]={}
        self.counter=0
        self.trade_id_counter=0
        
        
    def process_limit_order(self,order_id: int, price:int, quantity:int , side:Side)->list[Trade]:
        trades=[]
        opposite_side = self.ask_book if side == Side.BUY else self.bid_book
        own_side = self.bid_book if side == Side.BUY else self.ask_book
        
        self.counter+=1
        current_time=self.counter
        remaining_quantity=quantity
        
        while remaining_quantity>0:
            
            best_price=opposite_side.get_best_price()
            
            if best_price is None:
                break
        
            if side == Side.BUY and price < best_price:
                break
            if side == Side.SELL and price > best_price:
                break
            
            matched_order=opposite_side.peek_best_order()
            
            if matched_order is None or matched_order.is_cancelled:
                    opposite_side.pop_best_order()
                    continue

            assert matched_order.price is not None

            fill_quantity=min(remaining_quantity,matched_order.quantity)
            remaining_quantity-=fill_quantity

            self.trade_id_counter+=1
            trades.append(Trade(
                trade_id=self.trade_id_counter,
                maker_id=matched_order.order_id,
                taker_id=order_id,
                price=matched_order.price,
                quantity=fill_quantity,
                timestamp=current_time
            ))

            if fill_quantity==matched_order.quantity:
                opposite_side.pop_best_order()
            else:
                matched_order.quantity-=fill_quantity
                opposite_side.reduce_volume(matched_order.price, fill_quantity)
                
        
        
        if remaining_quantity > 0:
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
                
                
                
                    
        
            
        
                

            
        
        
        
        
        