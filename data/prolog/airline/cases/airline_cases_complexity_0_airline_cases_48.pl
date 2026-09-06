/* ----------  Statutory rules needed for this case ---------- */

/*  Oversize fee (within / between U.S., Puerto Rico, U.S. Virgin Islands, Canada) */
oversize_fee(Size, 0)        :- Size =< 62.
oversize_fee(Size, 30)       :- Size  > 62, Size =< 65.
oversize_fee(Size, 200)      :- Size  > 65, Size =< 115.

/*  Over-weight fee (within / between U.S., Puerto Rico, U.S. Virgin Islands, Canada) */
overweight_fee(Weight, 0)    :- Weight =< 50.
overweight_fee(Weight, 30)   :- Weight  > 50, Weight =< 53.
overweight_fee(Weight, 100)  :- Weight  > 53, Weight =< 70.
overweight_fee(Weight, 200)  :- Weight  > 70, Weight =< 100.

/*  Choose the higher of the 2 special-needs fees                     */
extra_fee(Size, Weight, Fee) :-
    oversize_fee(Size, O),
    overweight_fee(Weight, W),
    ( O >= W -> Fee = O ; Fee = W ).

/*  Base checked-bag fee for a Business class customer on a domestic itinerary */
base_checked_fee(Index, 0)   :- Index =:= 1 ; Index =:= 2.
base_checked_fee(3,      150).
base_checked_fee(Index, 200) :- Index >= 4.

/* ----------  Facts for David's itinerary and baggage --------------- */

/*  Checked bags are numbered in the order they will be processed. */
checked_bag(1, 103, 57).   /* 48 x 29 x 26 in, 57 lb  */
checked_bag(2,  63, 51).   /* 35 x 19 x  9 in, 51 lb  */
checked_bag(3,  63, 82).   /* 33 x 16 x 14 in, 82 lb  */
checked_bag(4,  64, 52).   /* 38 x 14 x 12 in, 52 lb  */

/*  Flight ticket price */
flight_fare(86).

/* ----------  Aggregate calculations ------------------------------- */

bag_total_fee(Index, Fee) :-
    checked_bag(Index, Size, Weight),
    base_checked_fee(Index, Base),
    extra_fee(Size, Weight, Extra),
    Fee is Base + Extra.

total_checked_bags_cost(Total) :-
    findall(F, (checked_bag(I,_,_), bag_total_fee(I, F)), List),
    sum_list(List, Total).

total_cost(Total) :-
    total_checked_bags_cost(Bags),
    flight_fare(Fare),
    Total is Bags + Fare.

/* ----------  Produce the answer ----------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.