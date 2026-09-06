/* --------------------------
   Statutory rules (excerpt)
   -------------------------- */

/* route classification for the case */
route(europe_us).    /* Phoenix - Brussels */

/* passenger class */
class(basic_economy).

/* ---- Checked-bag base fees for BASIC ECONOMY on the Europe<->US route ---- */
checked_bag_base_fee(1, basic_economy, europe_us, 75).
checked_bag_base_fee(2, basic_economy, europe_us, 100).
checked_bag_base_fee(3, basic_economy, europe_us, 200).
checked_bag_base_fee(N, basic_economy, europe_us, 200) :- N>=4.

/* ---- Oversize fees on the Europe<->US route ----
   Size = L+W+H inches                                             */
oversize_fee(europe_us, Size, 0)   :- Size =< 62.                       % within allowance
oversize_fee(europe_us, Size, 30)  :- Size > 62, Size =< 65.
oversize_fee(europe_us, Size, 150) :- Size > 65, Size =< 115.

/* ---- Over-weight fees -------------------------------------------- */
% 50 < wt =< 53  (applies to all routes / classes)
overweight_fee(_,       Wt, 30)  :- Wt > 50, Wt =< 53.

% 53 < wt =< 70 for BASIC ECONOMY on Europe<->US route = $100
overweight_fee(europe_us, Wt, 100) :- Wt > 53, Wt =< 70, class(basic_economy).

% =<50 lb is free
overweight_fee(_,       Wt, 0)   :- Wt =< 50.

/* For this case we won't exceed 70 lb, so higher brackets are omitted. */


/* ---------------
   Case facts
   --------------- */

/* Flight ticket price */
ticket_price(322).

/* Personal item - free (not listed as a checked bag) */
personal_item(backpack).

/* Checked bags: bag(ID, L, W, H, Weight_lbs) ------------------------ */
bag(1, 39, 21, 12, 59).
bag(2, 38, 15, 12, 52).
bag(3, 50, 33, 28, 51).
bag(4, 49, 35, 25, 51).

/* -----------------
   Derived measures
   ----------------- */

/* Sum of outside dimensions = size inches */
bag_size(ID, Size) :-
    bag(ID, L, W, H, _),
    Size is L+W+H.

/* Weight */
bag_weight(ID, Wt) :-
    bag(ID, _, _, _, Wt).

/* Highest of oversize / overweight fee */
highest_extra_fee(ID, ExtraFee) :-
    bag_size(ID, Size),
    bag_weight(ID, Wt),
    route(Route),
    oversize_fee(Route, Size, OverSizeFee),
    overweight_fee(Route, Wt, OverWtFee),
    ExtraFee is max(OverSizeFee, OverWtFee).

/* Checked-bag base fee by sequence number */
checked_bag_fee(ID, BaseFee) :-
    class(Class), route(Route),
    bag_index(ID, N),
    checked_bag_base_fee(N, Class, Route, BaseFee).

/* Establish ordinal position of each bag (1-based)                   */
bag_index(ID, N) :-
    findall(B, bag(B,_,_,_,_), List),
    sort(List, Sorted),      % IDs already 1..4, keeps order
    nth1(N, Sorted, ID).

/* Total fee per bag */
bag_total_fee(ID, TotalFee) :-
    checked_bag_fee(ID, Base),
    highest_extra_fee(ID, Extra),
    TotalFee is Base + Extra.

/* Sum of all bag fees */
all_bags_total(Total) :-
    findall(F, (bag(ID,_,_,_,_), bag_total_fee(ID,F)), Fees),
    sum_list(Fees, Total).

/* -------------------------
   Grand total for Thomas
   ------------------------- */
total_cost(Total) :-
    ticket_price(Tix),
    all_bags_total(BagFees),
    Total is Tix + BagFees.

/* -------------------------
   Query & output
   ------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.