/* ---------------  Bag-fee statutes (subset relevant to this case) --------------- */

/* base fee for a checked bag inside the U.S. when travelling First Class
      BagNo = 1,2 ........ complimentary
      BagNo = 3 .......... $150
      BagNo >= 4 ......... $200                                         */
base_fee(BagNo,Fee) :- BagNo =< 2, Fee is 0.
base_fee(3       ,150).
base_fee(BagNo  ,200) :- BagNo > 3.

/* size fee - domestic (U.S. / Canada / P.R. / V.I.)                        */
size_fee(Linear,0   ) :- Linear =< 62.
size_fee(Linear,30  ) :- Linear > 62,  Linear =< 65.
size_fee(Linear,200 ) :- Linear > 65,  Linear =< 115.

/* weight fee - First Class, domestic                                       */
weight_fee(free ,Wt,0   ) :- Wt =< 70.
weight_fee(free ,Wt,200 ) :- Wt  > 70, Wt =< 100.

weight_fee(charged,Wt,0  ) :- Wt =< 50.
weight_fee(charged,Wt,30 ) :- Wt >  50, Wt =< 53.
weight_fee(charged,Wt,100) :- Wt >  53, Wt =< 70.
weight_fee(charged,Wt,200) :- Wt >  70, Wt =< 100.

/* the 'excess-dimension' fee for a bag is the higher of weight vs size     */
excess_fee(Status,Wt,Linear,Fee) :-
    size_fee(Linear,SFee),
    weight_fee(Status,Wt,WFee),
    Fee is max(SFee,WFee).


/* ---------------  Facts describing Sarah's journey --------------- */

ticket_price(269).

/* every checked bag:  id, L, W, H, Weight                                   */
bag(2,44,22,19,64).
bag(3,36,16,13,51).
bag(4,38,23,19,53).
bag(5,40,17,15,58).
bag(6,54,31,26,62).
bag(7,33,22, 9,61).
bag(8,37,19, 9,52).
bag(9,44,24,15,71).
bag(10,41,22,17,51).
bag(11,38,14,12,97).

checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ---------------  Helper predicates --------------- */

/* linear size */
linear(BagId,Sum) :- bag(BagId,L,W,H,_), Sum is L+W+H.

/* choose any 2-element subset of a list */
choose_two(List,[A,B]) :-
    select(A,List,R1), select(B,R1,_), A @< B.

/* compute all fees for a given choice of the 2 complimentary bags */
fees_for_choice(FreeBags,TotalBagFees) :-
    checked_bag_ids(AllBags),
    subtract(AllBags,FreeBags,ChargedBags),

    /* ----- base fees (depend only on how many bags are charged) */
    length(ChargedBags,NCharged),
    ( NCharged=0 -> BaseFee = 0
    ; BaseFee is 150 + (NCharged-1)*200 ),

    /* ----- excess-dimension fees for every bag ---------------- */
    findall(Fee,
        (   member(B,AllBags),
            (   member(B,FreeBags) -> Status = free ; Status = charged ),
            bag(B,_,_,_,Wt), linear(B,Lin),
            excess_fee(Status,Wt,Lin,Fee)
        ),
        FeeList),
    sum_list(FeeList,ExcessFees),

    TotalBagFees is BaseFee + ExcessFees.

/* find the minimal possible total (bags + ticket) */
total_cost(Total) :-
    checked_bag_ids(Bags),
    choose_two(Bags,FreeBags),
    fees_for_choice(FreeBags,BagFees),
    ticket_price(Tix),
    Cost is BagFees + Tix,
    \+ ( choose_two(Bags,OtherFree),
         fees_for_choice(OtherFree,OtherBagFees),
         OtherBagFees + Tix < Cost ),
    Total = Cost.

/* ---------------  Query --------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.