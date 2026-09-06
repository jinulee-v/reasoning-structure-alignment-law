:- format("~w~n", ["Label: 3585"]).
/* ======================  Facts  ====================== */

/* ticket price */
flight_cost(695).

/* checked bags:  bag(Id,Length,Width,Height,Weight) */
bag(2,42,19,18,74).
bag(3,37,16,12,84).
bag(4,35,17,12,72).
bag(5,37,17,10,69).
bag(6,37,16,11,53).
bag(7,33,21,11,62).
bag(8,52,29,25,87).

/* list of all checked-bag IDs (carry-on is not listed) */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ======================  Statutory rules  ====================== */

/* (1) Bag-size sum */
dims_sum(L,W,H,S) :- S is L+W+H.

/* (2) Oversize fees - to / from China, Japan, S. Korea, Hong Kong, India,
       Australia, New Zealand                                            */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* (3) Over-weight fees - same region
       Thresh = 70 lb for complimentary bags, 50 lb for charged bags      */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh    -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 450 ).

/* (4) Penalty for a bag = higher of oversize vs overweight              */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,50,OW),
       Pen is max(OS,OW).

/* (5) Checked-bag base fees - Business Class on this route              */
bag_fee(1,0).          /* 1st checked bag               */
bag_fee(2,0).          /* 2nd checked bag               */
bag_fee(3,200).        /* 3rd checked bag               */
bag_fee(N,200) :- N>=4.   /* 4th and beyond             */

/* ======================  Cost engine  ====================== */

/* pick 2 different IDs (F1<F2) from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* put the 2 freebies in positions 1-2, keep the rest in original order */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,Rest),
       Ordered = [F1,F2|Rest].

/* total cost for one particular choice of freebies */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       bags_cost(Ordered,1,BagFees,Penalties),
       flight_cost(Tix),
       Total is Tix + BagFees + Penalties.

/* walk through ordered list accumulating fees / penalties */
bags_cost([],_,0,0).
bags_cost([Bag|Bs],Idx,FeeTot,PenTot) :-
       (Idx =< 2 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,BaseFee),
       penalty(Bag,Kind,Pen),
       Next is Idx+1,
       bags_cost(Bs,Next,RestFee,RestPen),
       FeeTot is BaseFee + RestFee,
       PenTot is Pen + RestPen.

/* compute minimal total cost over all ways of choosing the 2 freebies */
total_cost(Min) :-
       checked_bag_ids(L),
       findall(C,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,C)),
               Costs),
       min_list(Costs,Min).

/* ======================  Query  ====================== */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.