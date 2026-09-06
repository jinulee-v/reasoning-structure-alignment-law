/* ---------------  Facts about Linda's trip --------------- */
% ticket price
flight_ticket(204).

% route category (London -> San-Francisco)
route(europe_us).

% passenger cabin
cabin(basic_economy).

/* bags(Id, type, dims(L,W,H), weight(Lbs)). */
bag(1,  backpack , dims(18,13,9) ,  weight(5)  ).
bag(2,  luggage  , dims(38,12,14),  weight(51) ).
bag(3,  backpack , dims(50,32,29),  weight(62) ).
bag(4,  luggage  , dims(36,16,12),  weight(54) ).
bag(5,  backpack , dims(33,18,12),  weight(58) ).
bag(6,  backpack , dims(48,28,27),  weight(68) ).
bag(7,  luggage  , dims(53,28,29),  weight(65) ).
bag(8,  backpack , dims(34,20,9) ,  weight(51) ).
bag(9,  backpack , dims(38,14,12),  weight(60) ).
bag(10, backpack , dims(51,35,27),  weight(53) ).
bag(11, luggage  , dims(47,30,26),  weight(52) ).

/* ---------------  Carry-on qualification --------------- */
personal_item(dims(L,W,H)) :- L=<18, W=<14, H=<8.
carry_on_item(dims(L,W,H)) :- L=<22, W=<14, H=<9.

carry_on(BagId) :-
    bag(BagId,_,dims(L,W,H),weight(_)),
    carry_on_item(dims(L,W,H)),
    BagId = 1.          % we purposely mark only Bag #1 as carry-on

/* ---------------  Checked-bag order --------------- */
checked_bag_id_list(List) :-
    findall(Id, (bag(Id,_,_,_), \+ carry_on(Id)), BagIds),
    sort(BagIds, List).   % natural (ascending) order matches Linda's packing

bag_index(BagId, Index) :-
    checked_bag_id_list(List),
    nth1(Index, List, BagId).

/* ---------------  Base checked-bag fees --------------- */
base_checked_fee(europe_us, basic_economy, 1, 75).
base_checked_fee(europe_us, basic_economy, 2, 100).
base_checked_fee(europe_us, basic_economy, 3, 200).
base_checked_fee(europe_us, basic_economy, N, 200) :- N>=4.

/* ---------------  Oversize fees (Europe <-> U.S.) --------------- */
oversize_fee(_,DimSum,0)          :- DimSum =< 62.
oversize_fee(europe_us,DimSum,30) :- DimSum > 62, DimSum =< 65.
oversize_fee(europe_us,DimSum,150):- DimSum > 65, DimSum =< 115.

/* ---------------  Overweight fees --------------- */
% band 1 : >50 - 53 lbs
overweight_fee(_,Wt,0) :- Wt =< 50.
overweight_fee(_,Wt,30) :- Wt > 50, Wt =< 53.

% band 2 : >53 - 70 lbs   (Europe <-> U.S.)
overweight_fee(europe_us,Wt,100) :- Wt > 53, Wt =< 70.

/* ---------------  Utility --------------- */
max_val(A,B,Max) :- (A>=B -> Max=A ; Max=B).

/* ---------------  Fee for each bag --------------- */
bag_fee(BagId,0) :- carry_on(BagId).                 % carry-on is free
bag_fee(BagId,TotalFee) :-
    \+ carry_on(BagId),
    bag_index(BagId,Idx),
    cabin(Cabin),
    route(Route),
    bag(BagId,_,dims(L,W,H),weight(Wt)),
    DimSum is L+W+H,
    base_checked_fee(Route,Cabin,Idx,Base),
    oversize_fee(Route,DimSum,OverSizeFee),
    overweight_fee(Route,Wt,OverWeightFee),
    max_val(OverSizeFee,OverWeightFee,Extra),
    TotalFee is Base + Extra.

/* ---------------  Sum of all bag fees --------------- */
total_bag_fees(Sum) :-
    findall(Fee, (bag(Id,_,_,_), bag_fee(Id,Fee)), Fees),
    sum_list(Fees, Sum).

/* ---------------  Grand total --------------- */
total_cost(Total) :-
    flight_ticket(Ticket),
    total_bag_fees(BagSum),
    Total is Ticket + BagSum.

/* ---------------  Query --------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.