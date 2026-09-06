/* =========================================================
   Statutory reasoning - Robert (Rome -> New Orleans)
   First Class, trans-Atlantic itinerary
   ========================================================= */

/* ------------  Ticket price  ---------------------------- */
flight_cost(670).

/* ------------  Itinerary details ------------------------ */
/* Rome (Italy) to New Orleans (USA) is trans-Atlantic */
itinerary_region(europe_usa).

/* ------------  Passenger class -------------------------- */
passenger_class(first).

/* ------------  Checked bags ----------------------------- */
/* Only bags that must be checked are listed (id 2-11)      */
/* bag(Id, Length, Width, Height, Weight)                   */
bag(2, 48, 32, 23, 68).
bag(3, 38, 22, 11, 53).
bag(4, 34, 22, 10, 68).
bag(5, 35, 17, 12, 65).
bag(6, 38, 16, 10, 51).
bag(7, 38, 14, 13, 51).
bag(8, 51, 34, 28, 52).
bag(9, 35, 20,  9, 70).
bag(10,49, 28, 28, 58).
bag(11,35, 21,  9, 51).

/* list of all checked-bag IDs (for easy enumeration) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ------------  Size helpers ----------------------------- */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fee - Europe <-> U.S.                             
   0         : =< 62 in
   $30       : 62 < dim =< 65
   $150      : 65 < dim =< 115                                   */
oversize_fee(Sum,Fee) :-
    (   Sum =< 62  -> Fee = 0
    ;   Sum =< 65  -> Fee = 30
    ;   Sum =< 115 -> Fee = 150 ).

/* ------------  Over-weight fees ------------------------- */
/* Fee table (all values in U.S.$) - Europe/USA region     */
/*   >50-53 lbs : 30                                       
   >53-70 lbs : 100                                      
   >70-100 lbs: 200                                      */
overweight_fee(W,Limit,Fee) :-
    (   W =< Limit -> Fee = 0                            % within allowance
    ;   W =< 53    -> Fee = 30
    ;   W =< 70    -> Fee = 100
    ;   W =< 100   -> Fee = 200 ).

/* ------------  Penalty (oversize vs overweight) --------- */
/* For First Class on trans-Atlantic, complimentary bags have 70-lb limit
   Charged bags have 50-lb limit */
penalty(BagId,comp,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,70,OW),      % complimentary => 70-lb limit
    Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,50,OW),      % charged bag => 50-lb limit
    Pen is max(OS,OW).

/* ------------  Checked-bag base fees -------------------- */
/* First Class - Europe <-> U.S.                             
   Bag 1-3 : $0    (complimentary)                        
   Bag 4+  : $200  */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N>=4.

/* ------------  Combinatorics: pick 3 complimentary bags -*/
choose_three(List,F1,F2,F3) :-
    append(_, [F1|T1], List),
    append(_, [F2|T2], T1),
    member(F3, T2).

ordered_list(F1,F2,F3,Ordered) :-
    checked_bag_ids(All),
    select(F1,All,R1),
    select(F2,R1,R2),
    select(F3,R2,Rest),
    Ordered = [F1,F2,F3|Rest].         % freebies occupy positions 1-3

/* ------------  Cost for a particular free-bag choice ----*/
cost_for_choice(F1,F2,F3,Total) :-
    ordered_list(F1,F2,F3,Ordered),
    cost_bags(Ordered,1,BagFees,Penalties),
    flight_cost(Flight),
    Total is Flight + BagFees + Penalties.

/* walk through the ordered list, accumulating fees+penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
    (Idx =< 3 -> Type = comp ; Type = charged),
    bag_fee(Idx,Fee),
    penalty(Bag,Type,Pen),
    NextIdx is Idx+1,
    cost_bags(Bs,NextIdx,CostRest,PenRest),
    CostSum is Fee + CostRest,
    PenSum  is Pen + PenRest.

/* ------------  Find the minimal total cost --------------*/
compute_total(MinTotal) :-
    checked_bag_ids(L),
    findall(T,
            ( choose_three(L,F1,F2,F3),
              cost_for_choice(F1,F2,F3,T) ),
            Totals),
    min_list(Totals,MinTotal).

/* ------------  Query and report ------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.