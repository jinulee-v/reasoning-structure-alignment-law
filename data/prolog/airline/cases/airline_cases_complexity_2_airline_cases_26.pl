/*=============================================================
   American Airlines baggage-fee calculator
   Case: Emily - Austin (U.S.)  ->  Shanghai (China) - First
   ----------------------------------------------------------
   Goal:  print the minimum total trip cost (USD)
   taking into account (i) the ticket price,
   (ii) checked-bag base fees, and (iii) any oversize / overweight
   penalties, in line with the statutory tables supplied.
=============================================================*/


/*--------------  Trip-specific facts  -----------------------*/

/* ticket price */
flight_cost(858).

/* all bags:  bag(Id,Length,Width,Height,Weight)   */
/* Bag 1 is the small backpack that fits as carry-on */
bag(1, 18,13, 6,  6).  % This is carry-on, not checked
bag(2, 42,24,14, 89).
bag(3, 50,28,24, 95).
bag(4, 35,17,11, 52).
bag(5, 51,36,27, 64).
bag(6, 50,36,25, 53).
bag(7, 33,23, 9, 66).
bag(8, 37,19, 9, 81).
bag(9, 38,14,11, 64).
bag(10,38,16, 9, 52).
bag(11,40,26,15, 78).

/* list of checked-bag IDs in some stable order */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).



/*--------------  Statutory rules (U.S. <-> China) --------------*/

/* ---- helper: sum of outside dimensions ---- */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ---- oversize penalty (China / Japan / Korea / ... row) ---- */
oversize_fee(S,Fee) :-
        (   S =< 62        -> Fee = 0
        ;   S =< 65        -> Fee = 30
        ;   S =< 115       -> Fee = 200
        ;   Fee = 200).    % For sizes > 115 (though not applicable here)

/* ---- overweight penalty (region: to / from China) ---------
   'Thresh' is the free allowance in lbs (70 when complimentary,
   50 when it is a charged bag).                                    */
overweight_fee(W,Thresh,Fee) :-
        (   W =< Thresh    -> Fee = 0
        ;   W =< 53        -> Fee = 30
        ;   W =< 70        -> Fee = 100
        ;   W =< 100       -> Fee = 450
        ;   Fee = 450).    % For weights > 100 (though not applicable here)

/* ---- overall penalty: higher of the two ------------------- */
penalty(BagId,complimentary,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(Weight,70,OW),
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,S),
        oversize_fee(S,OS),
        overweight_fee(Weight,50,OW),
        Pen is max(OS,OW).

/* ---- base checked-bag fee for First Class (U.S.-China) ---- */
% First Class gets 1st, 2nd, and 3rd bags free
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N >= 4.          /* 4th and beyond */

/*--------------  Cost calculus helpers  ---------------------*/

/* choose any 3 distinct elements (F1<F2<F3) from a list */
choose_three(List,F1,F2,F3) :-
        append(_,[F1|T1],List),
        append(_,[F2|T2],T1),
        member(F3,T2).

/* re-order list so the 3 complimentary bags occupy slots 1-3 */
ordered_list(F1,F2,F3,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,R1),
        select(F2,R1,R2),
        select(F3,R2,Rest),
        Ordered = [F1,F2,F3|Rest].

/* accumulate fees & penalties over the ordered list */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
        (Idx =< 3 -> Type = complimentary ; Type = charged),
        bag_fee(Idx,BFee),
        penalty(Bag,Type,Pen),
        Next is Idx+1,
        cost_bags(Bs,Next,FeeRest,PenRest),
        FeeSum is BFee + FeeRest,
        PenSum is Pen + PenRest.

/* total cost for one particular choice of complimentary bags */
choice_total(F1,F2,F3,Total) :-
        ordered_list(F1,F2,F3,Ordered),
        cost_bags(Ordered,1,BagFees,Penalties),
        flight_cost(Ticket),
        Total is Ticket + BagFees + Penalties.

/* compute the minimum total over every 3-bag choice */
total_cost(Min) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_three(L,A,B,C),
                  choice_total(A,B,C,T) ),
                Totals),
        min_list(Totals,Min).

/*--------------  Query & output  -----------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]), halt.