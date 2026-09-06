/* ----------  Statutory rules that apply to this case  ---------- */
:- use_module(library(lists)).

/* 1 free checked bag for Main Plus; thereafter domestic bag fees   */
bag_base_fee(Order,0   ) :- Order =:= 1.          % 1st checked bag - free
bag_base_fee(2,        45).
bag_base_fee(3,        150).
bag_base_fee(Order,200) :- Order>=4.              % 4th bag and beyond

/* Oversize fees - travel wholly within the U.S.                    */
oversize_fee(Sum,0  )   :- Sum =< 62.
oversize_fee(Sum,30 )   :- Sum > 62, Sum =< 65.
oversize_fee(Sum,200)   :- Sum > 65, Sum =< 115.

/* Over-weight fees - travel wholly within the U.S.                 */
overweight_fee(W,0  )   :- W =< 50.
overweight_fee(W,30 )   :- W > 50, W =< 53.
overweight_fee(W,100)   :- W > 53, W =< 70.
overweight_fee(W,200)   :- W > 70, W =< 100.

/* For an oversize + over-weight bag charge only the higher extra   */
extra_fee(DimSum,Weight,Extra) :-
    oversize_fee(DimSum,OverSizeFee),
    overweight_fee(Weight,OverWtFee),
    Extra is max(OverSizeFee,OverWtFee).

bag_dim_sum(L,W,H,S) :- S is L+W+H.

/* -------------------------  Case facts  ------------------------- */
% bag(Id,Length,Width,Height,Weight)
bag(1,22,13,9 ,10).   % Carry-on - won't be checked
bag(2,46,28,25,73).
bag(3,41,21,16,53).
bag(4,43,27,23,63).
bag(5,36,18,11,53).
bag(6,36,16,12,53).
bag(7,34,16,13,52).
bag(8,36,14,13,91).
bag(9,34,22,9 ,53).
bag(10,48,31,29,51).
bag(11,34,18,11,86).

/* Item 1 is within the 22*14*9 carry-on limit                     */
carry_on(Id) :-
    bag(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* Checked bags are all bags except the carry-on                    */
checked_bag(Id) :- bag(Id,_,_,_,_), \+ carry_on(Id).

/* Order of checked bags (arbitrary but fixed)                       */
checked_order([2,3,4,5,6,7,8,9,10,11]).

bag_index(Id,Idx) :-
    checked_order(List),
    nth1(Idx,List,Id).

/* Cost of one checked bag                                           */
bag_cost(Id,Cost) :-
    checked_bag(Id),
    bag_index(Id,Order),
    bag(Id,L,W,H,Weight),
    bag_dim_sum(L,W,H,DimSum),
    bag_base_fee(Order,BaseFee),
    extra_fee(DimSum,Weight,Extra),
    Cost is BaseFee + Extra.

/* Sum of all checked-bag costs                                      */
total_checked_bags_cost(Total) :-
    findall(C, (checked_bag(Id), bag_cost(Id,C)), Cs),
    sum_list(Cs,Total).

/* Fare price                                                        */
ticket_cost(199).

/* ----------------  Grand-total owed by the passenger ------------- */
total_cost(Total) :-
    ticket_cost(TFare),
    total_checked_bags_cost(BagFees),
    Total is TFare + BagFees.

/* --------------------  Produce the answer  ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.