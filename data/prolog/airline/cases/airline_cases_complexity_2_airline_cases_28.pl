/* ==========  Facts describing the journey  ========== */
ticket_price(166).

class(business).
route(usa, europe).                /* Philadelphia (U.S.) -> Brussels (Europe) */

/* items that will be checked (carry-on is excluded)     */
/* bag(Id, Length, Width, Height, Weight).               */
bag(2,38,14,11,51).
bag(3,38,26,15,53).
bag(4,38,12,13,51).
bag(5,47,24,20,52).
bag(6,40,25,15,57).
bag(7,40,20,12,61).
bag(8,41,22,14,51).
bag(9,49,35,25,62).
bag(10,37,18,9,67).
bag(11,33,21,10,56).

/* ==========  General helpers  ========== */
size_sum(L,W,H,S) :- S is L+W+H.

/* choose K elements out of a list ---------------------------------------- */
combination(0,_,[]).
combination(K,[H|T],[H|R]) :- K>0, K1 is K-1, combination(K1,T,R).
combination(K,[_|T],R)    :- K>0, combination(K,T,R).

/* ==========  Baggage FEES (statutory rules)  ========== */

/* free checked-bag allowance for Business class */
free_checked_bags(2).

/* checked-bag fee on this route (Europe <-> U.S.) for Business class
   - 1st & 2nd: free, 3rd+: 200 USD                                   */
checked_bag_fee(Idx,0) :- free_checked_bags(N), Idx =< N.          /* within allowance */
checked_bag_fee(Idx,200) :- free_checked_bags(N), Idx > N.         /* excess bags    */

/* oversize fee (all routes to / from Europe) ----------------------------- */
oversize_fee(Sum,0)   :- Sum =< 62.
oversize_fee(Sum,30)  :- Sum > 62, Sum =< 65.
oversize_fee(Sum,150) :- Sum > 65, Sum =< 115.

/* overweight fee --------------------------------------------------------- */
/* complimentary bags may weigh up to 70 lb                                 */
overweight_fee(W,free,0) :- W =< 70.

overweight_fee(W,pay,0)   :- W =< 50.
overweight_fee(W,pay,30)  :- W > 50,  W =< 53.
overweight_fee(W,pay,100) :- W > 53,  W =< 70.

/* choose the HIGHER of over-size vs over-weight (if both apply) ----------- */
extra_fee(BagId,FreeSet,Fee) :-
    bag(BagId,L,W,H,Weight),
    size_sum(L,W,H,Sum),
    oversize_fee(Sum,OFee),
    (   member(BagId,FreeSet) -> overweight_fee(Weight,free,WFee)
    ;                           overweight_fee(Weight,pay ,WFee)
    ),
    Fee is max(OFee,WFee).

/* total fee for one bag = checked-bag fee + extra fee --------------------- */
bag_cost(Index,BagId,FreeSet,Cost) :-
    checked_bag_fee(Index,BagFee),
    extra_fee(BagId,FreeSet,Extra),
    Cost is BagFee + Extra.

/* ==========  compute the overall cost  ========== */
all_bag_ids([2,3,4,5,6,7,8,9,10,11]).

bags_total_cost(FreeSet,Total) :-
    all_bag_ids(All),
    exclude({FreeSet}/[X]>>member(X,FreeSet),All,ChargeBags),
    append(FreeSet,ChargeBags,Ordered),          /* checked-bag indices 1..10 */
    findall(C,
            (nth1(Idx,Ordered,Bid),
             bag_cost(Idx,Bid,FreeSet,C)),
            Costs),
    sum_list(Costs,Total).

/* choose the 2 free bags so that the payable amount is minimal ------------*/
minimum_bags_cost(MinCost,BestFreeSet) :-
    all_bag_ids(Ids),
    findall(Cost-Free,
            ( combination(2,Ids,Free),
              bags_total_cost(Free,Cost) ),
            Pairs),
    keysort(Pairs,[MinCost-BestFreeSet|_]).

/* finally: whole trip cost = ticket + baggage */
total_cost(Total) :-
    minimum_bags_cost(BagsCost,_FreeSet),
    ticket_price(Ticket),
    Total is Ticket + BagsCost.

/* ==========  Query & print result  ========== */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.