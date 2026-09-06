/*************************************************************************
*  American Airlines bag-fee calculator                                  *
*  Case - Linda : Doha (Qatar)  ->  Miami (U.S.) - First Class            *
*************************************************************************/

                    /* ----------  Flight data  ---------- */

flight_ticket(1022).                /* ticket price (USD) */
cabin(first).                       /* First Class */

route(qatar_us).                    /* "Between Qatar and U.S." */

                    /* ----------  All bags carried  ------- */
/* bag(Id,Length,Width,Height,Weight) - dimensions in inches, weight in lbs */

bag(1,22,11, 8,  7).      /* small backpack - candidate carry-on           */
bag(2,34,21,10, 59).
bag(3,51,31,30, 52).
bag(4,44,23,19, 70).
bag(5,40,19,18, 62).

                    /* ----------  Carry-on rules  ---------- */

carry_on_max(22,14,9).              /* max L x W x H for a carry-on bag */

/* a bag qualifies as carry-on if all three dimensions are within limits */
carry_on(Id) :-
    bag(Id,L,W,H,_),
    carry_on_max(MaxL,MaxW,MaxH),
    L =< MaxL,  W =< MaxW,  H =< MaxH.

                    /* ----------  Checked-bag list ---------- */

/* list of the 4 checked bags (exclude the single carry-on) */
checked_bag_ids(Ids) :-
    findall(B,(bag(B,_,_,_,_), \+ carry_on(B)), Ids).

                    /* ----------  Base checked-bag fees ---- */
/* 'Between Qatar and U.S.' - First Class
     - Bags 1-3 complimentary
     - Bag 4 and every bag after that: $200                          */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N >= 4.

                    /* ----------  Oversize fees ------------- */
/* all regions share the same inch-bands                            */
oversize_fee(DimSum,Fee) :-
       (   DimSum =< 62     -> Fee = 0
       ;   DimSum =< 65     -> Fee = 30
       ;   DimSum =< 115    -> Fee = 150).

                    /* ----------  Over-weight fees ---------- */
/* distinction: complimentary bags use a 70-lb limit, charged bags 50-lb */

overweight_fee(Weight,comp,Fee) :-           % complimentary bag
       (   Weight =< 70   -> Fee = 0
       ;   Weight =< 100  -> Fee = 200         % (>70-100)  - NOT accepted,
       ).                                       % but never reached in this case

overweight_fee(Weight,charged,Fee) :-        % charged bag
       (   Weight =< 50   -> Fee = 0
       ;   Weight =< 53   -> Fee = 30
       ;   Weight =< 70   -> Fee = 100
       ;   Weight =< 100  -> Fee = 200
       ).

                    /* ----------  Penalties ----------------- */
/* "The higher fee between oversize and overweight applies."        */
penalty(Id,Type,Penalty) :-
       bag(Id,L,W,H,Weight),
       DimSum is L+W+H,
       oversize_fee(DimSum,OS),
       overweight_fee(Weight,Type,OW),
       Penalty is max(OS,OW).

                    /* ----------  Ordering of bags ---------- */
/* Three bags are complimentary (positions 1-3), exactly **one** bag
   goes in position 4 (and therefore attracts both the $200 base fee
   and the 'charged' overweight schedule).

   We enumerate every way of choosing that single charged bag and pick
   the minimum total cost.                                           */

ordered_list(ChargedId,Ordered) :-
       checked_bag_ids(All),
       select(ChargedId,All,Complimentary),
       append(Complimentary,[ChargedId],Ordered).   % put charged bag last

                    /* ----------  Cost for a specific choice ----- */

cost_for_choice(ChargedId,Total) :-
       ordered_list(ChargedId,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_ticket(Tix),
       Total is Tix + CostBags + Penalties.

/* walk the ordered list, accumulating base fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 3 -> Type = comp ; Type = charged),
       bag_fee(Idx,BaseFee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is BaseFee + CostRest,
       PenSum  is Pen + PenRest.

                    /* ----------  Grand total -------------------- */

total_cost(MinTotal) :-
       checked_bag_ids(All),
       findall(T, (member(Bag,All), cost_for_choice(Bag,T)), Totals),
       min_list(Totals,MinTotal).

                    /* ----------  Query & Output ----------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.