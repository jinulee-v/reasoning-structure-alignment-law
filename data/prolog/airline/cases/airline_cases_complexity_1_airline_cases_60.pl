/* ------------  Statutory rules that apply to this itinerary ------------- */

/*  The trip is Premium-Economy, India  ->  U.S.
    - First 2 checked bags:            $0 each
    - 3rd bag and every bag thereafter $200 each                (base fee)
    - Over-weight fees (lbs) applicable world-wide on this route
          0-50           : $0
          >50-53          : $30
          >53-70          : $100
          >70-100         : $450
    - Over-size fees (linear inches) applicable India-route
          >62-65          : $30
          >65-115         : $200
    - When both over-size and over-weight apply, charge ONLY the higher one
*/

/* ------------------------------- Facts ---------------------------------- */

/*  bag(ID, Length, Width, Height, Weight).   Dimensions in inches, weight in lbs */
bag(1, 20, 13,  6,  6).      /* carry-on - will be ignored for checked-bag fees */
bag(2, 37, 15, 13, 84).
bag(3, 35, 18, 10, 59).
bag(4, 36, 18, 10, 56).
bag(5, 50, 31, 24, 56).
bag(6, 38, 12, 14, 83).
bag(7, 35, 18, 12, 52).
bag(8, 33, 16, 14, 90).

flight_ticket(316).          /* $316 fare */

/* --------------------------- Helper rules ------------------------------- */

/* total size of a bag (linear inches) */
bag_size(L, W, H, S) :- S is L+W+H.

/* ---------- over-size fee for India <-> US flights ---------- */
oversize_fee(S, Fee) :-
    (  S > 65            -> Fee = 200          %  >65 -115 in
    ;  S > 62            -> Fee = 30           %  >62 -65 in
    ;                       Fee = 0
    ).

/* ---------- over-weight fee (global table for this route) -------------- */
overweight_fee(W, Fee) :-
    (  W > 100           -> fail              % not accepted - impossible here
    ;  W > 70            -> Fee = 450
    ;  W > 53            -> Fee = 100
    ;  W > 50            -> Fee = 30
    ;                       Fee = 0
    ).

/* choose the higher of overweight / oversize (statute wording) */
surcharge(L, W, H, Weight, Fee) :-
    bag_size(L,W,H,S),
    oversize_fee(S, OS),
    overweight_fee(Weight, OW),
    ( OW >= OS -> Fee = OW ; Fee = OS ).

/* --------------------- base checked-bag fee ---------------------------- */
/* 1st & 2nd bag free; every bag afterwards $200                           */
base_bag_fee(Index, Fee) :-
    ( Index =< 2 -> Fee = 0
    ;               Fee = 200
    ).

/* ---------------- cost of each checked bag ----------------------------- */
bag_cost(Index, ID, Cost) :-
    bag(ID,L,W,H,Weight),
    ID \= 1,                                % ignore the carry-on
    base_bag_fee(Index, Base),
    surcharge(L,W,H,Weight, Surcharge),
    Cost is Base + Surcharge.

/* ---------------------------- bag list --------------------------------- */
/* Checked bags are all bags except #1, numbered in ascending ID order     */
checked_bag_index(1,2).
checked_bag_index(2,3).
checked_bag_index(3,4).
checked_bag_index(4,5).
checked_bag_index(5,6).
checked_bag_index(6,7).
checked_bag_index(7,8).

/* ------------------------ total for all bags --------------------------- */
total_bag_cost(Total) :-
    findall(Cost,
            (checked_bag_index(Index,ID), bag_cost(Index,ID,Cost)),
            Costs),
    sumlist(Costs, Total).

/* ------------------------- grand total --------------------------------- */
total_cost(Total) :-
    total_bag_cost(BagTotal),
    flight_ticket(Fare),
    Total is Fare + BagTotal.

/* ----------------------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.