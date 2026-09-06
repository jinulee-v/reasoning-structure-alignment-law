/* ----------  Statutory rules that apply to this case  ---------- */

/* Basic-Economy base fee for bags on an itinerary
   To / From India, China, Japan, South Korea, Hong Kong, Australia, New Zealand        */
base_fee(1,75).
base_fee(2,100).
base_fee(N,200) :- N>2.

/* --------  Over-WEIGHT fees (Basic Economy - To / From South Korea)  -------- */
overweight_fee(Weight,450) :- Weight > 70,    Weight =< 100.   /* 70-100 lbs  */
overweight_fee(Weight,100) :- Weight > 53,    Weight =< 70.    /* 53-70 lbs   */
overweight_fee(Weight, 30) :- Weight > 50,    Weight =< 53.    /* 50-53 lbs   */
overweight_fee(Weight,  0) :- Weight =< 50.                   /* =<50 - none  */

/* --------  Over-SIZE fees (To / From South Korea)  -------- */
oversize_fee(DimSum,200) :- DimSum > 65, DimSum =< 115.   /* >65-115 in */
oversize_fee(DimSum, 30) :- DimSum > 62, DimSum =< 65.    /* >62-65 in  */
oversize_fee(DimSum,  0) :- DimSum =< 62.                 /* =<62 - none */

/* If a bag is both over-size and over-weight, only the HIGHER of the two applies */
surcharge(Weight,DimSum,S) :-
    overweight_fee(Weight,OW), oversize_fee(DimSum,OS),
    ( OW >= OS -> S = OW ; S = OS ).

/* ---------------   FACTS FOR MICHAEL'S TRIP   --------------- */

/* Flight ticket */
ticket_price(522).

/* Carry-on (free) - not listed among checked bags */

/* checked_bag(Idx, Length, Width, Height, Weight). */
checked_bag(1,40,22,17,71).
checked_bag(2,36,17,11,59).
checked_bag(3,35,14,14,56).
checked_bag(4,35,21, 9,59).

/* ---------------   COMPUTATION   --------------- */

/* Dimension sum of a bag */
dim_sum(L,W,H,S) :- S is L+W+H.

/* Cost of one checked bag, given it is the N-th checked bag */
bag_cost(N,Cost) :-
    checked_bag(N,L,W,H,Weight),
    dim_sum(L,W,H,DS),
    base_fee(N,BF),
    surcharge(Weight,DS,S),
    Cost is BF + S.

/* Total checked-bag cost */
checked_bags_total(Total) :-
    findall(C, (checked_bag(N,_,_,_,_), bag_cost(N,C)), Cs),
    sum_list(Cs,Total).

/* Total trip cost = ticket + bags (no other special fees apply) */
total_cost(Total) :-
    ticket_price(Ticket),
    checked_bags_total(Bags),
    Total is Ticket + Bags.

/* ---------------   QUERY   --------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.