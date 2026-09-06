/* ----------  Statutory rules (only those relevant to this case) ---------- */

:- use_module(library(lists)).

/* the itinerary we have is Japan <-> U.S. */
route(japan_usa).

/* Main Plus customer: first 2 checked bags are free                */
/* - first bag is already free for Main Cabin on this route          */
/* - Main Plus adds 1 extra free bag (max 2 total free)              */
bag_base_fee(Index, 0)  :- Index =< 2.          /* bag #1 or #2  */
bag_base_fee(Index, 200):- Index  > 2.          /* bag #3 +      */

/* ---------------- Oversize fees (Japan <-> U.S.) ------------------ */
oversize_fee(japan_usa, Size, Fee) :-
        (   Size > 115                                -> fail     % not accepted (irrelevant here)
        ;   Size > 65                                 -> Fee = 200   % >65-115 in.
        ;   Size > 62                                 -> Fee = 30    % >62-65  in.
        ;   Fee = 0).

/* ---------------- Over-weight fees ------------------------------ */
overweight_fee(Weight, Fee) :-
        (   Weight > 100                              -> fail     % not accepted (irrelevant here)
        ;   Weight > 70                               -> Fee = 450   % 70-100 lb
        ;   Weight > 53                               -> Fee = 100   % >53-70 lb
        ;   Weight > 50                               -> Fee = 30    % >50-53 lb
        ;   Fee = 0).

/* pick the higher of over-size vs over-weight (0 if neither) */
extra_fee(Route, Size, Weight, Fee) :-
        oversize_fee(Route, Size, F1),
        overweight_fee(Weight,    F2),
        (F1 >= F2 -> Fee = F1 ; Fee = F2).

/* ----------------------- Passenger's bags ----------------------- */
/* bag(Number, Length, Width, Height, Weight) */
bag(1, 38, 12, 14, 80).
bag(2, 37, 15, 12, 64).
bag(3, 36, 25, 12, 51).
bag(4, 33, 19, 12, 53).
bag(5, 46, 21, 22, 68).
bag(6, 36, 16, 11, 51).
bag(7, 45, 27, 24, 52).

/* -------------------  Cost calculation predicates --------------- */
bag_cost(Index, Cost) :-
        bag(Index, L, W, H, Weight),
        Size is L + W + H,
        route(Route),
        bag_base_fee(Index, Base),
        extra_fee(Route, Size, Weight, Extra),
        Cost is Base + Extra.

baggage_cost(Total) :-
        findall(C, (bag(Index,_,_,_,_), bag_cost(Index, C)), Costs),
        sumlist(Costs, Total).

flight_cost(501).                % given in the fact pattern

total_cost(Total) :-
        flight_cost(F),
        baggage_cost(B),
        Total is F + B.

/* -----------------------  Produce the answer -------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.