import heapq
from abc import ABC, abstractmethod
from collections import deque

from .types import Order, Side


class BookSide(ABC):
    @abstractmethod
    def get_best_price(self)->int | None:
        pass
        
    @abstractmethod
    def add_order(self, order:Order)->None:
        pass
    
    @abstractmethod
    def peek_best_order(self)->Order | None:
        pass
    
    @abstractmethod
    def pop_best_order(self)->Order|None :
        pass
    
    @abstractmethod
    def get_top_levels(self, n:int )->list[tuple[int,int]]:
        pass
    
    @abstractmethod
    def is_empty(self)-> bool:
        pass
    @abstractmethod
    def reduce_volume(self, price: int, qty: int) -> None:
        pass
    
    
    
class HeapBookSide(BookSide):
    
    
    def __init__(self, side: Side):
        self.side = side
        self.heap: list[int] = []
        self.price_queue_dict: dict[int, deque[Order]] = {}
        self.volume_tracker: dict[int, int] = {}

    def _signed(self, price: int) -> int:
    
        return -price if self.side is Side.BUY else price

    
    def add_order(self, order: Order) -> None:
        assert order.price is not None, "a resting order must carry a price"
        if order.price not in self.price_queue_dict:
            self.price_queue_dict[order.price] = deque()
            self.volume_tracker[order.price] = 0
            heapq.heappush(self.heap, self._signed(order.price))

        self.price_queue_dict[order.price].append(order)
        self.volume_tracker[order.price] += order.quantity
        
    
    
    def peek_best_order(self) -> Order | None:
        self.clean_top()
        if not self.heap:
            return None
        price = self._signed(self.heap[0])
        return self.price_queue_dict[price][0]

    def pop_best_order(self) -> Order | None:
        self.clean_top()
        if not self.heap:
            return None
        price = self._signed(self.heap[0])
        order = self.price_queue_dict[price].popleft()
       
        if not order.is_cancelled:
            self.volume_tracker[price] -= order.quantity
        if not self.price_queue_dict[price]:
            heapq.heappop(self.heap)
            del self.price_queue_dict[price]
            del self.volume_tracker[price]
        return order

    def reduce_volume(self, price: int, qty: int) -> None:
        self.volume_tracker[price] -= qty

    def get_best_price(self) -> int | None:
        self.clean_top()
        if not self.heap:
            return None
        return self._signed(self.heap[0])

    def clean_top(self) -> None:
       
        while self.heap:
            price = self._signed(self.heap[0])
            if self.volume_tracker.get(price, 0) > 0:
                break
            heapq.heappop(self.heap)
            self.price_queue_dict.pop(price, None)
            self.volume_tracker.pop(price, None)

    def get_top_levels(self, n: int) -> list[tuple[int, int]]:
        
        levels: list[tuple[int, int]] = []
        for signed_price in sorted(self.heap):
            price = self._signed(signed_price)
            volume = self.volume_tracker.get(price, 0)
            if volume > 0:
                levels.append((price, volume))
            if len(levels) == n:
                break
        return levels

    def is_empty(self) -> bool:
        return self.get_best_price() is None


    




    
