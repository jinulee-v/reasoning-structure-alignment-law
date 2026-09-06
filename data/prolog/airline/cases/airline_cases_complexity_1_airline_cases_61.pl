/* ----------  RULES (encoded statutes relevant to this case)  ---------- */

% --------------------  flight / passenger facts  -----------------------
route(within_us).               % Houston - Denver
class(main_cabin).              % ticketed service class
ticket_price(277).              % USD

% --------------------  bag facts  --------------------------------------
% bag(ID, Length, Width, Height, Weight).  (dimensions in inches, weight in lbs)
bag(1, 18, 14, 7,  5).   % personal-item candidate
bag(2, 42, 20, 19, 81).
bag(3, 33, 21, 10, 86).
bag(4, 38, 21, 15, 89).
bag(5, 35, 17, 13, 53).
bag(6, 37, 19, 15, 65).
bag(7, 34, 17, 12, 51).
bag(8, 51, 33, 29, 57).

% --------------------  allowances  -------------------------------------
personal_item_max(18,14,8).

% personal_item(+BagId)  - true if bag qualifies as free personal item
personal_item(B) :-
    bag(B,L,W,H,_),
    personal_item_max(PL,PW,PH),
    L =< PL, W =< PW, H =< PH.

% --------------------  checked-bag base fee by ordinal ------------------
% checked_base_fee(+BagNumber, -Fee)
checked_base_fee(1,40).
checked_base_fee(2,45).
checked_base_fee(3,150).
checked_base_fee(N,200) :- N>=4.

% --------------------  oversize fee -------------------------------------
% oversize_fee(+BagId,-Fee)
oversize_fee(B,Fee) :-
    bag(B,L,W,H,_),
    S is L+W+H,
    (  S > 65  -> Fee = 200
    ;  S > 62  -> Fee = 30
    ;  Fee = 0 ).

% --------------------  overweight fee -----------------------------------
% overweight_fee(+BagId,-Fee)
overweight_fee(B,Fee) :-
    bag(B,_,_,_,Wt),
    (  Wt > 70         -> Fee = 200
    ;  Wt > 53         -> Fee = 100
    ;  Wt > 50         -> Fee = 30
    ;  Fee = 0 ).

% --------------------  extra fee (higher of over-size/weight)------------
extra_fee(B,Fee) :-
    oversize_fee(B,F1), overweight_fee(B,F2),
    Fee is max(F1,F2).

% --------------------  derive list of chargeable checked bags -----------
checked_bag_list(List) :-
    findall(B, (bag(B,_,_,_,_), \+ personal_item(B)), List).

% --------------------  total checked-bag charges ------------------------
checked_bags_cost(Cost) :-
    checked_bag_list(Bags),
    findall(BagCost,
        ( nth1(Idx,Bags,B),
          checked_base_fee(Idx,Base),
          extra_fee(B,Extra),
          BagCost is Base+Extra ),
        Costs),
    sum_list(Costs,Cost).

% --------------------  grand total  -------------------------------------
total_cost(Total) :-
    ticket_price(Tix),
    checked_bags_cost(BagFees),
    Total is Tix + BagFees.

                            /* ----------  QUERY ---------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.