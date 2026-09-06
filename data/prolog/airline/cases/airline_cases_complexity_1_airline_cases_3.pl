/*  ------------  RULES (statute encoding - only what is relevant to this case)  ------------ */

/* free checked-bag allowance for the given cabin / route */
free_bags(main_plus, europe_us, 2).     /* Main Plus = Main Cabin +1 extra (max 2) */

/* base checked-bag fees (after free allowance)  - Europe <-> U.S. */
base_bag_fee(_, Index, Class, europe_us, 0) :-
    free_bags(Class, europe_us, Free),
    Index =< Free.
base_bag_fee(_, Index, Class, europe_us, 200) :-
    free_bags(Class, europe_us, Free),
    Index  > Free.

/* oversize fees - Europe table */
oversize_fee(SumDim, Fee) :-
    (   SumDim =< 62 -> Fee = 0
    ;   SumDim =< 65 -> Fee = 30
    ;   SumDim =< 115 -> Fee = 150
    ).

/* overweight fees - Europe table (values valid while weight =< 70 lbs) */
overweight_fee(Weight, Fee) :-
    (   Weight =< 50 ->  Fee = 0
    ;   Weight =< 53 ->  Fee = 30
    ;   Weight =< 70 ->  Fee = 100
    ).

/* the extra charge that applies when both oversize and overweight */
extra_fee(SumDim, Weight, Extra) :-
    oversize_fee(SumDim, O),
    overweight_fee(Weight, W),
    (O >= W -> Extra = O ; Extra = W).

/* complete fee for one checked bag */
bag_total_fee(Index, L,W,H,Weight, Class, Route, Total) :-
    SumDim is L+W+H,
    base_bag_fee(Index, Index, Class, Route, Base),
    extra_fee(SumDim, Weight, Extra),
    Total is Base + Extra.

/* -----------------------  FACTS (the present case)  ----------------------- */

passenger_class(main_plus).
route(europe_us).             /* Los Angeles <-> Paris */
flight_ticket_cost(550).

/* checked bags (carry-on item is not listed here)            */
/* bag(Index, Length, Width, Height, Weight) */
bag(1, 37,17,10,55).
bag(2, 41,23,13,52).
bag(3, 39,16,13,53).
bag(4, 34,21,10,56).
bag(5, 34,18,13,51).
bag(6, 46,27,23,69).
bag(7, 40,18,16,52).

/* -----------------------  COMPUTATION  ----------------------- */

bags_total_cost(TotalBagsCost) :-
    passenger_class(Class),
    route(Route),
    findall(Fee,
            ( bag(Index,L,W,H,Weight),
              bag_total_fee(Index,L,W,H,Weight,Class,Route,Fee)
            ),
            Fees),
    sum_list(Fees, TotalBagsCost).

total_cost(Total) :-
    bags_total_cost(Bags),
    flight_ticket_cost(Tix),
    Total is Bags + Tix.

/* -----------------------  QUERY (print result)  ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.