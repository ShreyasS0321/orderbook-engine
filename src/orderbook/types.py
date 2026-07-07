from dataclasses import dataclass
from enum import Enum

PRICE_SCALE=10**5

class Side(Enum):
    
    BUY=1
    SELL=2

class OrderType(Enum):
    
    LIMIT=1
    MARKET=2

@dataclass(slots=True)
class Order:
    order_id: int 
    side: Side
    quantity:int
    timestamp:int
    order_type: OrderType
    is_cancelled:bool =False
    price: int | None = None 
    
    def __post_init__(self)->None:
        
        if self.quantity<=0:
        
            raise ValueError("quantity must be positive")
        if self.order_type is OrderType.LIMIT and self.price is None:
            
                raise ValueError("Order Type Limit must have a price associated")
            
        if self.order_type is OrderType.MARKET and self.price is not None:

                raise ValueError("Order Type Market must have no price associated")

            
    
    
@dataclass(slots=True,frozen=True)
class Trade:
    
    trade_id:int
    maker_id:int
    taker_id:int
    price:int
    quantity:int
    timestamp:int
    
def to_ticks(price:float)->int:
    
    return round(price*PRICE_SCALE)

def from_ticks(price:int)->float:
    return  price/PRICE_SCALE