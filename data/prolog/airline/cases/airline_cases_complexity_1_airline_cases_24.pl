/* =========  Statutory rules used in this case  ========= */

/* passenger, itinerary and ticket */
passenger(mary).
itinerary(mary, boston, xiamen).              % U.S. -> China
class(mary, main_cabin).
ticket_price(mary, 1375).

/* ----------------  Mary's items  ----------------
   bag(ID , Length, Width, Height, Weight). */
bag(1, 20, 14,  8,  9).      % qualifies as carry-on
bag(2, 43, 22, 19, 60).
bag(3, 47, 26, 18, 57).
bag(4, 36, 15, 12, 51).
bag(5, 41, 25, 16, 60).
bag(6, 45, 34, 22, 53).
bag(7, 43, 31, 19, 52).
bag(8, 44, 19, 18, 63).

/* =========  Carry-on rules (1 personal item + 1 carry-on)  ========= */
carry_on_limit(22,14,9).   % 22 x 14 x 9 in.

is_carry_on(ID) :-
    bag(ID,L,W,H,_),
    carry_on_limit(CL,CW,CH),
    L =< CL, W =< CW, H =< CH.

/* All bags that are NOT carry-on are checked */
checked_bag(ID) :-
    bag(ID,_,_,_,_),
    \+ is_carry_on(ID).

/* =========  Dimension helpers  ========= */
dim_sum(ID,Sum) :-
    bag(ID,L,W,H,_),
    Sum is L+W+H.

/* =========  Overweight surcharges (U.S. <-> China)  ========= */
overweight_fee(ID,Fee) :-
    bag(ID,_,_,_,Wt),
    ( Wt > 50, Wt =< 53 -> Fee = 30
    ; Wt > 53, Wt =< 70 -> Fee = 100
    ; Wt > 70, Wt =< 100 -> Fee = 450
    ;                            Fee = 0 ).

/* =========  Oversize surcharges (U.S. <-> China)  ========= */
oversize_fee(ID,Fee) :-
    dim_sum(ID,S),
    ( S > 62, S =< 65  -> Fee = 30
    ; S > 65, S =< 115 -> Fee = 200
    ;                         Fee = 0 ).

/* =========  Total surcharge for a bag  =========
   If both overweight and oversize apply, only the HIGHER one is charged. */
bag_surcharge(ID,S) :-
    oversize_fee(ID,OS),
    overweight_fee(ID,OW),
    ( OS >= OW -> S = OS ; S = OW ).

/* =========  Base checked-bag fees (U.S. <-> China, Main Cabin)  ========= */
base_checked_fee(Order,Fee) :-       % Order starts at 1
    class(mary, main_cabin),
    ( Order =:= 1 -> Fee = 0
    ; Order =:= 2 -> Fee = 100
    ; Order >= 3  -> Fee = 200 ).

/* =========  Cost of all checked bags  ========= */
checked_bag_list(List) :-
    findall(ID, checked_bag(ID), List).

checked_bags_cost(Total) :-
    checked_bag_list(List),
    checked_bags_cost(List, 1, 0, Total).

checked_bags_cost([], _, Acc, Acc).
checked_bags_cost([ID|Rest], Ord, Acc0, Total) :-
    base_checked_fee(Ord, Base),
    bag_surcharge(ID, Surch),
    Acc1 is Acc0 + Base + Surch,
    Ord1 is Ord + 1,
    checked_bags_cost(Rest, Ord1, Acc1, Total).

/* =========  Grand total (ticket + all bag fees)  ========= */
total_cost(Total) :-
    checked_bags_cost(Bags),
    ticket_price(mary, Ticket),
    Total is Ticket + Bags.

/* =========  Query and output  ========= */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.