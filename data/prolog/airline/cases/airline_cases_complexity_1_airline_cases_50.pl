/* ----------  Statutory rules we need for this case ---------- */

/* route(jessica, Route) - Jessica is travelling between the U.S. and Europe */
route(jessica, us_europe).

/* travel_class(jessica, Class) - Jessica is a First-class passenger */
travel_class(jessica, first).

/* Ticket price */
ticket_price(jessica, 498).

/* ----------  Jessica's bags (only checked ones are listed) ----------
   checked_bag(Idx, Len, W, Hgt, Weight).
   Idx = order in which the bags are checked.
*/
checked_bag(1, 34,17,13,52).
checked_bag(2, 49,30,27,59).
checked_bag(3, 39,26,18,54).
checked_bag(4, 52,35,26,51).
checked_bag(5, 34,16,14,51).
checked_bag(6, 36,21,12,60).
checked_bag(7, 49,36,24,51).

/* ----------  BASE FEE rules for First-class, U.S.<->Europe ---------- */
base_fee(first, us_europe, Order, 0)  :- Order =< 3.      % 1st-3rd bags
base_fee(first, us_europe, Order, 200):- Order >  3.      % 4th bag onward

/* ----------  OVERSIZE fees to / from Europe ---------- */
oversize_fee(us_europe, Dim, 0)   :- Dim =< 62.
oversize_fee(us_europe, Dim, 30)  :- Dim > 62, Dim =< 65.
oversize_fee(us_europe, Dim, 150) :- Dim > 65, Dim =< 115.

/* ----------  OVERWEIGHT fees, U.S.<->Europe ---------- */
overweight_fee(_,    W, 0)   :- W =< 50.
overweight_fee(_,    W, 30)  :- W > 50, W =< 53.
overweight_fee(_,    W, 100) :- W > 53, W =< 70.

/* ----------  Choose the applicable extra fee (higher of the two) ---------- */
extra_fee(Route, Dim, W, Extra) :-
    oversize_fee(Route, Dim, OSize),
    overweight_fee(Route, W, OWeight),
    (OSize >= OWeight -> Extra = OSize ; Extra = OWeight).

/* ----------  Dimension helper (length+width+height) ---------- */
dimension(L, W, H, Dim) :- Dim is L+W+H.

/* ----------  Cost of one checked bag ---------- */
bag_cost(Order, L, Wd, H, Wt, Cost) :-
    dimension(L, Wd, H, Dim),
    route(jessica, Route),
    travel_class(jessica, Class),
    base_fee(Class, Route, Order, Base),
    extra_fee(Route, Dim, Wt, Extra),
    Cost is Base + Extra.

/* ----------  Sum the cost of all checked bags ---------- */
all_bags_cost(Sum) :-
    findall(C,
            (checked_bag(N,L,W,H,WT), bag_cost(N,L,W,H,WT,C)),
            Costs),
    sum_list(Costs, Sum).

/* ----------  Total cost = ticket + bags ---------- */
total_cost(Total) :-
    ticket_price(jessica, Ticket),
    all_bags_cost(BagCost),
    Total is Ticket + BagCost.

/* ----------  Show result ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.