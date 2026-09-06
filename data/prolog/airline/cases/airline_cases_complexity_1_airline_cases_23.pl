/* === Statutory rules that matter for this case === */

/*  The itinerary is Business Class, U.S. -> Peru (South America, except Panama).
    - 1st-2nd checked bags: $0 (complimentary)
    - 3rd checked bag:      $200
    - Each bag 4+ :         $200
    Weight limits
       - Complimentary bags : 70 lb
       - Charged bags       : 50 lb
    Over-weight surcharges
       50< W =<53 lb  -> $30
       53< W =<70 lb  -> $100
       70< W =<100 lb -> $200
    Over-size surcharges (South America rules)
       62< Sigmadim =<65 in  -> $30
       65< Sigmadim =<115 in -> $150
    If a bag is both over-weight and over-size, charge only the higher of the two.
*/

complimentary_bags(2).

/* base fee for the N-th checked bag */
bag_base_fee(N,0 ) :- N =< 2, !.
bag_base_fee(_,200).

/* weight limit depends on whether the bag is complimentary */
weight_limit(N,70) :- N =< 2, !.
weight_limit(_,50).

/* over-weight surcharge */
overweight_fee(N,W,0) :- weight_limit(N,L), W =< L, !.
overweight_fee(_,W,30) :- W  =< 53, W  > 50, !.
overweight_fee(_,W,100):- W  =< 70, W  > 53, !.
overweight_fee(_,W,200):- W  =<100, W  > 70.

/* over-size surcharge */
oversize_fee(D,0)   :- D =< 62, !.
oversize_fee(D,30)  :- D =< 65, D > 62, !.
oversize_fee(D,150) :- D =<115, D > 65.

/* choose the higher of the 2 surcharges */
surcharge(N,W,D,S) :-
    overweight_fee(N,W,OW),
    oversize_fee(D,OS),
    ( OW >= OS -> S = OW ; S = OS ).

/* total fee for one bag */
bag_cost(N,W,D,C) :-
    bag_base_fee(N,BF),
    surcharge(N,W,D,S),
    C is BF + S.

/* === Facts for Michael's trip === */

/* bag(ID,Weight(lb),Sum_of_dimensions(in)) */
bag(bag2,51,65).
bag(bag3,95,67).
bag(bag4,67,63).
bag(bag5,53,84).
bag(bag6,63,63).
bag(bag7,72,65).
bag(bag8,53,65).

/* We order the bags so as to minimise charges:
   the 2 heaviest (but =<70 lb) become the complimentary bags. */
bag_order(1,bag4).
bag_order(2,bag6).
bag_order(3,bag3).
bag_order(4,bag5).
bag_order(5,bag7).
bag_order(6,bag2).
bag_order(7,bag8).

/* convenience predicate */
bag_position(ID,N) :- bag_order(N,ID).

/* cost per bag in that position */
bag_total_cost(N,C) :-
    bag_order(N,ID),
    bag(ID,W,D),
    bag_cost(N,W,D,C).

/* sum all bag costs */
bags_cost(Total) :-
    findall(C, bag_total_cost(_,C), L),
    sum_list(L,Total).

/* Flight ticket price */
ticket_cost(557).

/* === Overall total === */
total_cost(Total) :-
    bags_cost(Bags),
    ticket_cost(Ticket),
    Total is Bags + Ticket.

/* === Query === */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.