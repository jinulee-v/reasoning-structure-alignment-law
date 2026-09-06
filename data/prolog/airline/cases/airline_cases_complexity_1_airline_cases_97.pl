/* ---------------  Rules derived from the statutes --------------- */

% passenger data
passenger(michael).
class(michael, premium_economy).               % Premium Economy Class
itinerary(michael, within_us).                 % Phoenix - Chicago
ticket_cost(michael, 75).                      % USD

/* --------------  Bags the passenger is travelling with ----------- */
/* bag(Id, Length, Width, Height, Weight).  (all dimensions in inches, weight in lbs) */

bag(bag1, 20, 11,  9,  8).      % qualifies as 1 carry-on  (free)
bag(bag2, 47, 26, 20, 52).
bag(bag3, 39, 12, 15, 54).
bag(bag4, 42, 23, 16, 78).
bag(bag5, 35, 19, 10, 90).
bag(bag6, 37, 13, 14, 51).
bag(bag7, 45, 33, 20, 53).
bag(bag8, 33, 18, 14, 53).

/* --------------  Helper predicates --------------------------------*/

size_in_inches(L, W, H, S) :- S is L+W+H.

/* oversize fee (Within / between U.S., Puerto Rico, U.S.V.I., Canada)  */
oversize_fee(Size, 0)   :- Size =< 62.
oversize_fee(Size, 30)  :- Size > 62, Size =< 65.
oversize_fee(Size, 200) :- Size > 65, Size =< 115.

/* overweight fee - Within / between U.S., Puerto Rico, U.S.V.I., Canada */
overweight_fee(W, 0)    :- W =< 50.
overweight_fee(W, 30)   :- W > 50,  W =< 53.
overweight_fee(W, 100)  :- W > 53,  W =< 70.
overweight_fee(W, 200)  :- W > 70,  W =< 100.

/* choose the higher of the two (if both zero -> zero) */
extra_fee(Size, Weight, Fee) :-
    oversize_fee(Size, OS),
    overweight_fee(Weight, OW),
    ( OS >= OW -> Fee = OS ; Fee = OW ).

/* base checked-bag fee for Premium Economy, travel within U.S. */
base_checked_fee(Idx, 0)   :- Idx = 1 ; Idx = 2.
base_checked_fee(3, 150).
base_checked_fee(Idx, 200) :- Idx >= 4.

/* -------------  Selecting which bags are checked ------------------*/

/* bag1 is carry-on (free) - all others are checked                */
checked_bag_order(Order, BagID) :-
    % list of checked bags in traveling order
    Bags = [bag2,bag3,bag4,bag5,bag6,bag7,bag8],
    nth1(Order, Bags, BagID).

/* -------------  Bag-by-bag cost calculation -----------------------*/
checked_bag_cost(Idx, BagID, Cost) :-
    checked_bag_order(Idx, BagID),
    bag(BagID, L, W, H, Weight),
    size_in_inches(L,W,H,Size),
    base_checked_fee(Idx, Base),
    extra_fee(Size, Weight, Extra),
    Cost is Base + Extra.

/* -------------  Total cost ----------------------------------------*/
total_bag_fees(Total) :-
    findall(C, checked_bag_cost(_,_,C), Costs),
    sum_list(Costs, Total).

total_cost(Total) :-
    passenger(michael),
    ticket_cost(michael, Ticket),
    total_bag_fees(BagFees),
    Total is Ticket + BagFees.

/* -------------  Query & output ------------------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.