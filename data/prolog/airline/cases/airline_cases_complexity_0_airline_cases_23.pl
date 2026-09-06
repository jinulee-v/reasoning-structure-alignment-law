/* ---------- Rules (statutes) -------------------------------------------- */

/* route category for the itinerary */
route_cat(new_orleans, ottawa, us_canada).

/* cabin of the passenger */
cabin(first_class).

/* ---------- Passenger's bags (facts) ------------------------------------ */
/* bag(Id, Length, Width, Height, Weight).  Length,Width,Height in inches, 
   Weight in pounds */
bag(1,22,14,8 ,12).
bag(2,49,26,23,52).
bag(3,51,33,29,51).
bag(4,35,20,10,52).
bag(5,36,15,12,52).

/* Bag 1 is used as the single free carry-on item */
carry_on(1).

checked_bag(BagId) :-
    bag(BagId,_,_,_,_),
    \+ carry_on(BagId).

/* -----------------  FEES  ------------------------------------------------ */

/* ---- base checked-bag fee (depends on order) ---- */
base_fee(Index, first_class, us_canada, 0)  :- Index =< 2, !.
base_fee(3,      first_class, us_canada, 150) :- !.
base_fee(Index,  first_class, us_canada, 200) :- Index >= 4.

/* ---- oversize fees (U.S. <-> Canada) ---- */
oversize_fee(us_canada, Dim, 0)   :- Dim =< 62, !.
oversize_fee(us_canada, Dim, 30)  :- Dim =< 65, !.          /* 62-65 in */
oversize_fee(us_canada, Dim, 200) :- Dim =< 115, !.

/* ---- overweight fees (only ranges that occur in the case) ---- */
overweight_fee(_Route, W, 0)   :- W =< 50, !.
overweight_fee(_Route, W, 30)  :- W  =< 53, !.               /* 50-53 lb */
overweight_fee(us_canada, W,100):- W  =< 70, !.

/* for each checked bag compute its total fee */
checked_bag_fee(BagId, Fee) :-
    cabin(Cabin), route_cat(new_orleans, ottawa, Route),
    /* order of this checked bag */
    findall(Id, checked_bag(Id), List),
    sort(List, Sorted),               /* order by Id (1 ... 5)               */
    nth1(Index, Sorted, BagId),       /* Index starts at 1                  */
    base_fee(Index, Cabin, Route, Base),

    /* size and weight */
    bag(BagId,L,W,H,Weight),
    Dim is L+W+H,

    oversize_fee(Route, Dim, OSize),
    overweight_fee(Route, Weight, OWeight),
    Extra is max(OSize,OWeight),

    Fee is Base + Extra.

/* sum of all bag fees */
total_bag_fees(Total) :-
    findall(F, (checked_bag(B), checked_bag_fee(B,F)), List),
    sum_list(List, Total).

/* overall cost = ticket + bag fees */
ticket_price(268).

total_cost(Total) :-
    ticket_price(T),
    total_bag_fees(Bags),
    Total is T + Bags.

/* ---------------   query   ---------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.