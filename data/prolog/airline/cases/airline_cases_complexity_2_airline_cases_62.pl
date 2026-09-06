/*****************************************************************
  Statutory rules (subset needed for this case)
*****************************************************************/

% complimentary checked-bag allowance for Business Class
free_checked_bags(business,2).

% base checked-bag fee for Business Class Europe <-> U.S.
% BagNumber counts only checked bags (1,2,3,...)
base_checked_fee(BagNumber,business,Fee) :-
    free_checked_bags(business,Free),
    ( BagNumber =< Free -> Fee = 0       % within free allowance
    ; Fee = 200                          % 3rd bag and above
    ).

/* -------------------------------------------------------------
   Oversize fees  (Europe <-> U.S. / Puerto Rico / etc.)
   size = L+W+H in inches
----------------------------------------------------------------*/

oversize_fee(Size,Fee) :-
          Size =< 62 ,      Fee = 0  ;                 % not oversize
    ( 62 <  Size, Size =< 65 , Fee = 30 )  ;
    ( 65 <  Size, Size =<115 , Fee =150 ).

/* -------------------------------------------------------------
   Over-weight fees  (Europe <-> U.S. for Business Class)
----------------------------------------------------------------*/
% limit for complimentary bags = 70 lbs
overweight_fee(BagNumber,Weight,Fee) :-
    free_checked_bags(business,Free),
    ( BagNumber =< Free -> Limit = 70              % complimentary bag
    ;                Limit = 50                    % other bags
    ),
    ( Weight =< Limit                         -> Fee = 0
    ; Weight  =< 53                           -> Fee = 30  % 50<wt<=53
    ; Weight  =< 70                           -> Fee =100  % 53<wt<=70
    ; Fee = 99999 ).                                     % not accepted - never used here

/* -------------------------------------------------------------
   Total charge for a single checked bag
----------------------------------------------------------------*/
bag_charge(BagNumber,Size,Weight,Charge) :-
    oversize_fee(Size,OFee),
    overweight_fee(BagNumber,Weight,WFee),
    MaxFee is max(OFee,WFee),          % "higher of oversize or overweight"
    base_checked_fee(BagNumber,business,Base),
    Charge is Base + MaxFee.

/*****************************************************************
  Facts for James's journey
*****************************************************************/

ticket_price(599).

/*   bag(Id,Length,Width,Height,Weight).  */
bag(1, 18,13, 9, 12).     % carry-on
bag(2, 54,32,28, 52).
bag(3, 39,18,13, 51).
bag(4, 45,24,22, 51).
bag(5, 35,14,14, 51).
bag(6, 36,14,14, 53).
bag(7, 42,18,18, 65).
bag(8, 34,18,11, 51).
bag(9, 46,26,18, 51).
bag(10,38,13,12, 51).
bag(11,49,36,26, 67).

/*  Checked-bag sequence we will use (carry-on #1 is not listed)  */
checked_sequence([2,3,4,5,6,7,8,9,10,11]).

/*****************************************************************
  Computation of total cost
*****************************************************************/

% helper: sum of list
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,S1), S is S1+H.

% produce list of per-bag charges, then sum them
total_bag_fees(Total) :-
    checked_sequence(List),
    findall(Fee,
            ( nth1(N,List,BagID),
              bag(BagID,L,W,H,Weight),
              Size is L+W+H,
              bag_charge(N,Size,Weight,Fee)
            ),
            Fees),
    sum_list(Fees,Total).

total_cost(Total) :-
    ticket_price(Ticket),
    total_bag_fees(BagFees),
    Total is Ticket + BagFees.

/*****************************************************************
  Query & output
*****************************************************************/
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.