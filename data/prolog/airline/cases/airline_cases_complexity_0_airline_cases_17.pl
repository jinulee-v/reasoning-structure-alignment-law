/* =========================================================
   Statutory rules needed for the present case
   ========================================================= */

/* ----- route classification (Charlotte - Montreal) */
route(charlotte, montreal, us_canada).

/* ----- passenger and fare type */
passenger(daniel).
fare_class(daniel, main_plus).

/* ----- "Main Plus" gives 1 extra free checked bag          */
/*     (treated as the 1st checked bag)                      */
extra_free_bags(main_plus, 1).

/* ----- base checked-bag fees for the route U.S.-Canada ----- */
base_checked_fee(us_canada, 1, 35).
base_checked_fee(us_canada, 2, 45).
base_checked_fee(us_canada, 3, 150).
base_checked_fee(us_canada, N, 200) :- N >= 4.

/* ----- overweight fees (lbs) - U.S./Canada route ---------- */
overweight_fee(us_canada, W, 0)   :- W =< 50.
overweight_fee(us_canada, W, 30)  :- W  > 50, W =< 53.
overweight_fee(us_canada, W, 100) :- W  > 53, W =< 70.
overweight_fee(us_canada, W, 200) :- W  > 70, W =< 100.

/* ----- oversize fees (total inches) - U.S./Canada route ---- */
oversize_fee(us_canada, S, 0)   :- S =< 62.
oversize_fee(us_canada, S, 30)  :- S  > 62, S =< 65.
oversize_fee(us_canada, S, 200) :- S  > 65, S =< 115.

/* for each bag, the greater of the oversize / overweight fee applies */
extra_bag_fee(Route, W, S, Fee) :-
        overweight_fee(Route, W, OW),
        oversize_fee(Route, S, OS),
        (OW >= OS -> Fee = OW ; Fee = OS).

/* =========================================================
   Facts describing Daniel's items
   ========================================================= */

item(1, personal_item,   18,14,7,   9).          /* free - personal item */
item(2, checked,         40,16,17, 85).
item(3, checked,         41,20,20, 59).
item(4, checked,         33,21,11, 77).
item(5, checked,         40,26,20, 52).

/* =========================================================
   Utility predicates
   ========================================================= */

/* total outside dimension of a bag */
size_sum(L,W,H,S) :- S is L+W+H.

/* list of all checked bags (order as given) */
checked_bag_list(List) :-
        findall(ID, (item(ID, checked,_,_,_,_)), List).

/* base fee for bag number N, taking free-bag entitlement into account */
effective_base_fee(Passenger, Route, N, Fee) :-
        fare_class(Passenger, Class),
        extra_free_bags(Class, FreeN),
        (N =< FreeN
          -> Fee = 0                       /* waived */
          ;  (base_checked_fee(Route, N, Fee))).

/* fee for one checked bag in position N */
bag_total_fee(Passenger, Route, N, BagID, TotalFee) :-
        item(BagID, checked, L,W,H, WT),
        size_sum(L,W,H, S),
        effective_base_fee(Passenger, Route, N, Base),
        extra_bag_fee(Route, WT, S, Extra),
        TotalFee is Base + Extra.

/* sum fees for all checked bags */
checked_bags_cost(Passenger, Route, Total) :-
        checked_bag_list(List),
        checked_bags_cost(Passenger, Route, List, 1, Total).

checked_bags_cost(_, _, [], _, 0).
checked_bags_cost(P, R, [B|Bs], N, Total) :-
        bag_total_fee(P, R, N, B, FeeB),
        N1 is N+1,
        checked_bags_cost(P, R, Bs, N1, Rest),
        Total is FeeB + Rest.

/* flight ticket price */
ticket_price(daniel, 105).

/* Daniel's complete total */
total_cost(Total) :-
        passenger(daniel),
        route(charlotte, montreal, Route),
        checked_bags_cost(daniel, Route, BagsCost),
        ticket_price(daniel, Ticket),
        Total is Ticket + BagsCost.

/* =========================================================
   Query
   ========================================================= */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.