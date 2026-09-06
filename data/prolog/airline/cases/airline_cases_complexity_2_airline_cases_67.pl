/* ============================================================
   American Airlines - baggage cost calculator
   Case: Sarah (First Class) - Hong Kong -> Austin
   Ticket price : $1,209
   ============================================================ */

/* ------------- carry-on limits -------------------------------- */
carry_on_max(22,14,9).

/* ------------- passenger's items ------------------------------ */
/* bag(Id,Length,Width,Height,Weight) */
bag(1,22,12, 9,11).     /* qualifies as the single carry-on           */
bag(2,40,28,15,51).
bag(3,38,17,10,53).
bag(4,38,26,13,63).
bag(5,35,21, 9,67).
bag(6,33,20,10,57).
bag(7,48,32,26,51).
bag(8,39,25,13,71).
bag(9,39,25,18,95).
bag(10,37,25,12,51).
bag(11,53,31,26,99).

/* ------------- ticket price ----------------------------------- */
flight_cost(1209).

/* ------------- helper: does the bag fit the carry-on sizer? ---- */
carry_on(Id) :-
    bag(Id,L,W,H,_),
    carry_on_max(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

/* ------------- list of checked bags --------------------------- */
checked_bag_ids(Ids) :-
    findall(Id,(bag(Id,_,_,_,_), \+ carry_on(Id)),Ids).

/* ------------- size (L+W+H) ----------------------------------- */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ------------- oversize fee - to / from Hong Kong ------------- */
/* Sum =<62 in -> 0 ; 62<Sum=<65 -> 30 ; 65<Sum=<115 -> 200            */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* ------------- overweight fee - to / from Hong Kong ----------- */
/* threshold parameter = 50 lb for charged bags, 70 lb for comp.  */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh    -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 450 ).

/* ------------- penalty (max of overweight / oversize) --------- */
penalty(Id,comp,Pen) :-
       bag(Id,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),           % complimentary bag -> 70-lb limit
       Pen is max(OS,OW).

penalty(Id,charged,Pen) :-
       bag(Id,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),           % charged bag -> 50-lb limit
       Pen is max(OS,OW).

/* ------------- checked-bag base fee (First Class) ------------- */
/* 1st-3rd bag free, 4th+ = $200                                  */
bag_fee(Position,0)    :- Position =< 3.
bag_fee(Position,200)  :- Position  > 3.

/* ------------- choose three distinct elements from a list ----- */
choose_three(List,A,B,C) :-
       append(_,[A|Tail1],List),
       append(_,[B|Tail2],Tail1),
       member(C,Tail2),
       A \= B, A \= C, B \= C.

/* ------------- put the three freebies first in order ---------- */
ordered_list(A,B,C,Ordered) :-
       checked_bag_ids(All),
       select(A,All,R1),
       select(B,R1,R2),
       select(C,R2,R3),
       Ordered = [A,B,C|R3].

/* ------------- cost for one particular choice of freebies ----- */
cost_for_choice(A,B,C,Total) :-
       ordered_list(A,B,C,Checked),
       cost_bags(Checked,1,BagFees,Penalties),
       flight_cost(Tix),
       Total is Tix + BagFees + Penalties.

/* accumulate bag fees (+) penalties walking through list         */
cost_bags([],_,0,0).
cost_bags([Id|Rest],Pos,BagSum,PenSum) :-
       (Pos =< 3 -> Type = comp ; Type = charged),
       bag_fee(Pos,BF),
       penalty(Id,Type,Pen),
       NextPos is Pos + 1,
       cost_bags(Rest,NextPos,BagRest,PenRest),
       BagSum is BF + BagRest,
       PenSum is Pen + PenRest.

/* ------------- minimal total cost across all choices ---------- */
compute_total(MinCost) :-
       checked_bag_ids(L),
       findall(Cost,
               ( choose_three(L,A,B,C),
                 cost_for_choice(A,B,C,Cost)),
               Costs),
       min_list(Costs,MinCost).

/* ------------- query & print result --------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.