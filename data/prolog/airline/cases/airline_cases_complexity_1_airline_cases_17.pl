/* ------------  FACTS  ------------ */
% price of the ticket
ticket_price(340).

% cabin and itinerary (Portland, U.S.  ->  Nagoya, Japan)
cabin(main_cabin).
route(portland, nagoya).                  % U.S.  to / from Japan

% Mary's pieces (No, Length, Width, Height, Weight)
bag(1,21,13, 6,  9).      % will be carry-on
bag(2,37,18, 9, 83).
bag(3,38,18,12, 64).
bag(4,36,18,16, 55).
bag(5,50,34,23, 70).
bag(6,47,33,22, 57).
bag(7,40,19,15, 69).
bag(8,43,20,20, 51).

/* ------------  RULES  ------------ */
% carry-on (fits 22*14*9)
carryon(N) :- bag(N,L,W,H,_), L=<22, W=<14, H=<9.

% list of checked bags in the order of their bag numbers
checked_bag_list(List) :-
    findall(N, (bag(N,_,_,_,_), \+ carryon(N)), List).

/* Base checked-bag fee for U.S.<->Japan, Main Cabin         */
base_bag_fee(1,0).
base_bag_fee(2,100).
base_bag_fee(N,200) :- N>=3.

/* Oversize fee : U.S.<->Japan                               */
oversize_fee(Size,0 ) :- Size=<62.
oversize_fee(Size,30) :- Size>62, Size=<65.
oversize_fee(Size,200) :- Size>65, Size=<115.

/* Over-weight fee : U.S.<->Japan                            */
overweight_fee(W, 0  ) :- W=<50.
overweight_fee(W, 30 ) :- W>50, W=<53.
overweight_fee(W, 100) :- W>53, W=<70.
overweight_fee(W, 450) :- W>70, W=<100.

/* Extra fee for an individual bag                           */
bag_extra_fee(N,Extra) :-
    bag(N,L,W,H,Weight),
    Size  is L+W+H,
    oversize_fee(Size,SizeFee),
    overweight_fee(Weight,WeightFee),
    Extra is max(SizeFee,WeightFee).

/* Total fee for a particular checked bag (base+extra)       */
bag_total_fee(Index, BagNo, Fee) :-
    base_bag_fee(Index,Base),
    bag_extra_fee(BagNo,Extra),
    Fee is Base+Extra.

/* Sum of all checked-bag fees                               */
total_bag_fees(Total) :-
    checked_bag_list(List),
    findall(F,
            (nth1(Index,List,BagNo),
             bag_total_fee(Index,BagNo,F)),
            Fees),
    sum_list(Fees,Total).

/* ----------------  FINAL ANSWER  -------------------------- */
total_cost(Total) :-
    total_bag_fees(BagFees),
    ticket_price(Ticket),
    Total is Ticket + BagFees.

:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.