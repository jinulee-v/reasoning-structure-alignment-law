/* ---------- Statutory rules (subset needed for this case) ---------- */

/* Robert is Main Plus on a U.S. <-> Haiti itinerary
   -> he gets 2 free checked bags (Main Cabin allowance 1 + Main Plus extra 1) */
free_checked_bags(2).

/* Base checked-bag fee (after the free allowance)               */
base_bag_fee(Index, 0)   :- free_checked_bags(F), Index =< F.           /* 1st-2nd bag */
base_bag_fee(Index, 200) :- free_checked_bags(F), Index  > F.           /* 3rd bag +   */

/* Over-WEIGHT surcharges - Caribbean <-> U.S. table                  */
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W > 50,  W =< 53.
overweight_fee(W, 100) :- W > 53,  W =< 70.
overweight_fee(W, 200) :- W > 70,  W =< 100.

/* Over-SIZE surcharges - Caribbean <-> U.S. table                    */
oversize_fee(S, 0)   :- S =< 62.
oversize_fee(S, 30)  :- S > 62, S =< 65.
oversize_fee(S, 200) :- S > 65, S =< 115.

/* For each bag, the higher of the two surcharges applies           */
surcharge(W, S, Fee) :-
    overweight_fee(W, OW),
    oversize_fee(S,  OS),
    (OW >= OS -> Fee = OW ; Fee = OS).

/* ---------- Facts for Robert's bags (only checked bags) ---------- */
/* bag(Index, Length, Width, Height, Weight)                         */
bag(1, 36, 13, 14, 62).
bag(2, 38, 22, 12, 66).
bag(3, 44, 25, 21, 59).
bag(4, 38, 13, 14, 95).
bag(5, 52, 34, 26, 76).
bag(6, 34, 19, 12, 51).
bag(7, 37, 12, 14, 75).

/* ---------- Fee calculation for every bag ------------------------ */
bag_fee(Index, Fee) :-
    bag(Index, L, W, H, Weight),
    SizeSum is L + W + H,
    base_bag_fee(Index, Base),
    surcharge(Weight, SizeSum, Surch),
    Fee is Base + Surch.

/* ---------- Aggregate baggage fees ------------------------------ */
:- use_module(library(lists)).

total_baggage_fees(Total) :-
    findall(F, bag_fee(_, F), Fs),
    sum_list(Fs, Total).

/* ---------- Ticket price ---------------------------------------- */
flight_ticket(93).

/* ---------- Final total ----------------------------------------- */
total_cost(Total) :-
    total_baggage_fees(Bags),
    flight_ticket(Tix),
    Total is Bags + Tix.

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.