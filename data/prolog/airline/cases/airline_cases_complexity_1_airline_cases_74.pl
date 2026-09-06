/* ----------  Rules from the statutes that we need for this case ---------- */

:- use_module(library(lists)).

/* flight information */
flight_ticket(187).
passenger_class(first).          /* Susan is First Class           */
free_checked_bags(2).            /* Domestic First -> 1st & 2nd bag */

/* ---------------  Data describing Susan's pieces of luggage ------------- */
/* bag(Id, Length, Width, Height, Weight).  Dimensions in inches, weight in lbs */

bag(b2, 45,20,20, 52).
bag(b3, 52,34,25, 86).
bag(b4, 35,18,11, 54).
bag(b5, 41,21,16, 51).
bag(b6, 38,13,14, 67).
bag(b7, 37,13,13, 52).
bag(b8, 33,18,14, 51).

/* ----------------------  Helper predicates  ----------------------------- */

/* linear_dimension(+Id, -TotalInches) */
linear_dimension(Id, Dim) :-
    bag(Id,L,W,H,_), Dim is L+W+H.

/* oversize_fee(+Dim, -Fee)  - within / between U.S. */
oversize_fee(Dim, Fee) :-
    (Dim =< 62 -> Fee = 0
    ;Dim =< 65 -> Fee = 30
    ;Dim =< 115 -> Fee = 200).

/* overweight_fee(+Weight, +FreeFlag, -Fee) */
overweight_fee(W, free, Fee) :-
    (W =< 70 -> Fee = 0           % free bags can weigh up to 70 lb
    ;W =< 100 -> Fee = 200).      % 70-100 lb
overweight_fee(W, charged, Fee) :-
    (   W =< 50 -> Fee = 0
    ;   W =< 53 -> Fee = 30
    ;   W =< 70 -> Fee = 100
    ;   W =< 100 -> Fee = 200).

/* bag_base_fee(+IndexAmongCharged, -Fee)   - domestic First class */
bag_base_fee(1,150).        % 3rd checked bag overall
bag_base_fee(N,200) :- N>=2.% 4th, 5th ... checked bags

/* cost_of_bag(+Id,+FreeFlag,+ChargedIndex,-Cost) */
cost_of_bag(Id, FreeFlag, _, Cost) :-
    FreeFlag = free,
    linear_dimension(Id,Dim),
    oversize_fee(Dim,OFee),
    bag(Id,_,_,_,W),
    overweight_fee(W,free,WFee),
    MaxFee is max(OFee,WFee),
    Cost is MaxFee.

cost_of_bag(Id, charged, Index, Cost) :-
    bag_base_fee(Index,BagFee),
    linear_dimension(Id,Dim),
    oversize_fee(Dim,OFee),
    bag(Id,_,_,_,W),
    overweight_fee(W,charged,WFee),
    MaxFee is max(OFee,WFee),
    Cost is BagFee + MaxFee.

/* -----------------  Selecting the complimentary bags  ------------------- */

/* combination of 2 distinct elements */
two_bags(List, A, B, Rest) :-
    select(A,List,R1),
    select(B,R1,Rest),
    A @< B.               /* avoid duplicates (order doesn't matter) */

/* cost_for_choice(+FreeList,-Cost) */
cost_for_choice(FreeList, Cost) :-
    bags(AllBags),
    subtract(AllBags,FreeList,ChargedBags),
    % costs of the two complimentary bags
    findall(C1,(member(B,FreeList),
                cost_of_bag(B,free,_,C1)),FreeCosts),
    sumlist(FreeCosts,CostFree),
    % costs of the remaining (charged) bags
    findall(C2,
            (nth1(Index,ChargedBags,B),
             cost_of_bag(B,charged,Index,C2)), ChargedCosts),
    sumlist(ChargedCosts,CostCharged),
    Cost is CostFree + CostCharged.

/* list of all checked bags (carry-on is not included here) */
bags([b2,b3,b4,b5,b6,b7,b8]).

/* total_cost(-Total)  -  minimal possible total the passenger must pay */
total_cost(Total) :-
    flight_ticket(Ticket),
    bags(BagList),
    findall(Cost,
            (two_bags(BagList,Free1,Free2,_),
             cost_for_choice([Free1,Free2],BagCost),
             Cost is Ticket + BagCost),
            Costs),
    min_list(Costs, Total).

/* ---------------------------  Query  ------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.