/* -------------  Statutory rules (simplified to what we need ------------- */

/* size of a bag */
size_sum(L,W,H,S) :- S is L+W+H.

/* ---------------- Oversize fees : to / from South Korea ----------------- */
/* South-Korea is treated the same as 'To or from China, Japan, South Korea,
   Hong Kong, India, Australia and New Zealand' in the statute            */

oversize_fee(S,0)   :- S =< 62.                         /* within limit    */
oversize_fee(S,30)  :- S  > 62, S =< 65.               /* 62-65 in / 158-165 cm */
oversize_fee(S,200) :- S  > 65, S =< 115.              /* 65-115 in / 165-292 cm */

/* ---------------- Over-weight fees : to / from South Korea ------------- */
overweight_fee(W,0)    :- W =< 50.                     /* up to 50 lb      */
overweight_fee(W,30)   :- W  > 50, W =< 53.            /* 50-53 lb          */
overweight_fee(W,100)  :- W  > 53, W =< 70.            /* 53-70 lb          */
overweight_fee(W,450)  :- W  > 70, W =< 100.           /* 70-100 lb         */

/* ---------------- Base checked-bag fee for Main Cabin ------------------ */
/* 1st bag is free when travelling to / from South-Korea (statute)         */
base_checked_fee(1,0).         /* 1st bag (complimentary)                 */
base_checked_fee(2,100).       /* 2nd bag                                 */
base_checked_fee(N,200) :- N>=3. /* 3rd and each additional bag           */

/* The additional charge that applies to a bag is the HIGHER of the two   */
extra_charge(L,W,H,Weight,Charge) :-
        size_sum(L,W,H,S),
        oversize_fee(S,OSFee),
        overweight_fee(Weight,OWFee),
        (OSFee >= OWFee -> Charge = OSFee ; Charge = OWFee).

/* Cost of a particular checked bag (identified by its sequence number)   */
bag_cost(BagNumber,L,W,H,Weight,Cost) :-
        base_checked_fee(BagNumber,Base),
        extra_charge(L,W,H,Weight,Extra),
        Cost is Base + Extra.

/* ------------------------  CASE FACTS  --------------------------------- */

ticket_cost(484).

/* Checked bags only - the small 18*11*7 backpack is the personal item    */
/* bag(Index,Length,Width,Height,Weight).                                 */
bag(1,33,19,12,99).
bag(2,33,19,13,53).
bag(3,37,19,9 ,51).
bag(4,39,19,17,51).
bag(5,36,19,17,59).
bag(6,37,19,14,53).
bag(7,37,14,14,52).
bag(8,35,21,9 ,51).
bag(9,40,20,14,53).
bag(10,44,23,17,63).

/* --------------------  Total baggage cost ------------------------------ */
checked_bags_total(Total) :-
        findall(Cost,
                (bag(N,L,W,H,Weight),
                 bag_cost(N,L,W,H,Weight,Cost)),
                Costs),
        sum_list(Costs,Total).

total_cost(Total) :-
        checked_bags_total(Bags),
        ticket_cost(Ticket),
        Total is Bags + Ticket.

/* -------------------   Query and display result ------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.