:- use_module(library(lists)).     % for sumlist/2

/*-------------------------------------------------
   Basic facts about the trip
-------------------------------------------------*/

flight_cost(269).                 % ticket price in dollars
passenger_class(first).           % First Class
route(domestic).                  % Washington, D.C. -> San Francisco

/*-------------------------------------------------
   Bags                          bag(Id,L,W,H,Weight)
-------------------------------------------------*/
bag(1,20,14,9, 6).
bag(2,36,18,10,76).
bag(3,41,28,19,60).
bag(4,34,20,9,74).
bag(5,46,19,22,68).

/*-------------------------------------------------
   Carry-on rules (exactly 1 permitted)
-------------------------------------------------*/
carry_on_bag(Id) :-
    bag(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9,
    Id = 1.                      % this is the only bag that meets the limit

/*-------------------------------------------------
   Checked bags (all that aren't the carry-on)
-------------------------------------------------*/
checked_bag(Id) :- bag(Id,_,_,_,_), \+ carry_on_bag(Id).

/* Order in which the checked bags are counted */
bag_order(2,1).
bag_order(3,2).
bag_order(4,3).
bag_order(5,4).

/*-------------------------------------------------
   Base fee for a checked bag in First Class,
   Washington-D.C. <-> San-Francisco (domestic)
-------------------------------------------------*/
base_fee(Order,0)  :- member(Order,[1,2]).  % 1st & 2nd are free
base_fee(3,150).
base_fee(Order,200) :- Order >= 4.

/*-------------------------------------------------
   Oversize fee (domestic)
-------------------------------------------------*/
oversize_fee(Dim,0)    :- Dim =< 62.
oversize_fee(Dim,30)   :- Dim  > 62, Dim =< 65.
oversize_fee(Dim,200)  :- Dim  > 65, Dim =< 115.

/*-------------------------------------------------
   Over-weight fee (domestic, First Class)
   First-Class complimentary limit = 70 lbs
-------------------------------------------------*/
overweight_fee(W,0)    :- W =< 70.
overweight_fee(W,200)  :- W  > 70.

/*-------------------------------------------------
   Extra fee = higher of oversize / overweight
-------------------------------------------------*/
extra_fee(Dim,W,Extra) :-
    oversize_fee(Dim,OS),
    overweight_fee(W,OW),
    ( OS >= OW -> Extra = OS ; Extra = OW ).

/*-------------------------------------------------
   Fee for each checked bag
-------------------------------------------------*/
bag_fee(Id,Fee) :-
    checked_bag(Id),
    bag(Id,L,W,H,Weight),
    Dim is L+W+H,
    bag_order(Id,Order),
    base_fee(Order,Base),
    extra_fee(Dim,Weight,Extra),
    Fee is Base + Extra.

/*-------------------------------------------------
   Total of all checked-bag fees
-------------------------------------------------*/
total_bag_fees(Total) :-
    findall(F,bag_fee(_,F),Fs),
    sumlist(Fs,Total).

/*-------------------------------------------------
   Grand total = ticket + bags
-------------------------------------------------*/
total_cost(Total) :-
    flight_cost(Ticket),
    total_bag_fees(Bags),
    Total is Ticket + Bags.

/*-------------------------------------------------
   Query
-------------------------------------------------*/
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.