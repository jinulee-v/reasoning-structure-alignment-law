/* ---------------  Statutory rules relevant to this case --------------- */

% passenger, class and journey region
passenger(william).
class(basic_economy).
region(australia_nz).                 % 'To / from Australia and New Zealand'
ticket_price(847).                    % given in the case

/* --------------------  Bags the passenger is travelling with -------------------- */
% bag(ID, Length, Width, Height, Weight_lbs)
bag(1,20,14, 8,10).   % this will be the 1 allowed carry-on
bag(2,49,26,23,51).
bag(3,33,22, 9,51).
bag(4,36,21,10,59).
bag(5,33,16,14,52).

/* --------------------  Determining which bag is carry-on -------------------- */
% 1 personal item wasn't supplied, so bag 1 is treated as the single carry-on
carry_on_bag(1).

checked_bag(Id) :- bag(Id,_,_,_,_), \+ carry_on_bag(Id).

/* ---------------- Oversize and overweight surcharges (Australia / NZ region) ---------------- */

% linear dimension of a bag
dimension(Id,D) :- bag(Id,L,W,H,_), D is L+W+H.

% oversize fee for the Australia / NZ region
oversize_fee(Id,Fee) :-
    dimension(Id,D),
    (   D > 65 -> Fee = 200          % 65-115 in / $200
    ;   D > 62 -> Fee = 30           % 62-65 in  / $30
    ;   Fee = 0).

% overweight fee (all regions use same brackets / amounts for these weights)
overweight_fee(Id,Fee) :-
    bag(Id,_,_,_,Wt),
    (   Wt > 53 -> Fee = 100         % 53-70 lbs
    ;   Wt > 50 -> Fee = 30          % 50-53 lbs
    ;   Fee = 0).

% when both apply take only the higher one
surcharge(Id,Fee) :-
    oversize_fee(Id,O),
    overweight_fee(Id,W),
    (O >= W -> Fee = O ; Fee = W).

/* ---------------- Base checked-bag fee sequence for Basic-Economy, Australia/NZ ---------------- */
% base_fee(BagNumber, Fee)
base_fee(1,75).
base_fee(2,100).
base_fee(3,200).
base_fee(N,200) :- N>=4.

/* ---------------- Cost of each checked bag ---------------- */
bag_cost(SeqNum, BagId, Cost) :-
    checked_bag(BagId),
    base_fee(SeqNum,Base),
    surcharge(BagId,S),
    Cost is Base + S.

/* ---------------- Total of all checked bags ---------------- */
total_checked_bag_fee(Total) :-
    findall(B,checked_bag(B),BsUnordered),
    sort(BsUnordered,Bs),                  % sequence them 2,3,4,5
    bag_costs(Bs,1,0,Total).

bag_costs([],_,Acc,Acc).
bag_costs([Bag|Rest],Seq,Acc0,Total) :-
    bag_cost(Seq,Bag,C),
    Acc1 is Acc0 + C,
    Seq1 is Seq + 1,
    bag_costs(Rest,Seq1,Acc1,Total).

/* ---------------- Grand total ---------------- */
total_cost(Total) :-
    total_checked_bag_fee(BagFee),
    ticket_price(Ticket),
    Total is Ticket + BagFee.

/* ---------------- Query and output ---------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.